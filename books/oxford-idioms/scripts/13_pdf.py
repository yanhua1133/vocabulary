"""Pass 13: 把 out/牛津习语词典.md 排成 pdf/牛津习语词典.pdf（16 开 185×260mm 竖版）。

成品 md 里本来就是内嵌 HTML 的四列表格，套上打印样式直接打就行。
渲染器和版式约束沿用 GRE3000 那本踩出来的经验，注释里标了「别改」的都是坑：

- **必须用 playwright 自带的 Chromium**。系统 Chrome 被企业策略
  （`enrollment-domain=gitlab.com`）禁掉了 headless 打印，`--print-to-pdf` 会静默
  什么都不写，让人拿着旧文件当成功。
- **量行数的页面必须 `viewport=609px` + `emulate_media("print")`**，
  否则量的是 1280px 屏幕布局，跟打印结果两样，会假报「0 个超行」。
- **行数不能估算**，`td.scrollHeight` 是整行高度、由最高的格子决定，用它判断会全错；
  只能用 Range 的行盒按 top 聚类，才是这一格自己占的行数。

Usage: 13_pdf.py [--sample]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
PDF = os.path.join(ROOT, "pdf")
WORK = os.path.join(ROOT, "work", "html")
PAGE = {"width": "185mm", "height": "260mm",
        "margin": {"top": "13mm", "bottom": "13mm", "left": "11mm",
                   "right": "11mm"}}

SHRINK_JS = """
() => {
  const MIN = 4.2 * 96 / 72;
  let over = 0;
  const rows = (td) => {
    const r = document.createRange();
    r.selectNodeContents(td);
    const tops = [...r.getClientRects()]
      .filter(x => x.height > 0).map(x => x.top).sort((a, b) => a - b);
    if (!tops.length) return 0;
    let n = 1, last = tops[0];
    for (const t of tops) { if (t - last > 4) { n++; last = t; } }
    return n;
  };
  const shrink = (td) => {                    // 返回 false 表示已到字号下限
    for (const el of [td, ...td.querySelectorAll('*')]) {
      const s = parseFloat(getComputedStyle(el).fontSize) * 0.93;
      if (s < MIN) return false;
      el.style.fontSize = s + 'px';
    }
    return true;
  };
  document.querySelectorAll('tbody td').forEach(td => {
    // 例句列最宽、内容也最长，允许三行；其余三列压两行
    // （都卡两行的话例句会被缩到 4pt 上下，根本没法看）
    if (td.colSpan > 1) return;               // 字母分隔行
    // 列宽调匀之后四列基本都能压进两行；只有习语列里那些带 BrE/AmE 变体的
    // 超长条目（`against your better ˈjudgement (especially BrE) (AmE usually…`）
    // 放不下，给它留第三行——占比不到 1%，比缩到 4.2pt 看不清强
    const MAX = td.cellIndex === 0 ? 3 : 2;
    let guard = 0;
    while (rows(td) > MAX && guard++ < 40 && shrink(td)) {}
    if (rows(td) > MAX) {
      // 缩到下限还放不下：例句的中英文改成连排，省掉一整行
      const br = td.querySelector('br');
      if (br) {
        br.replaceWith(document.createTextNode('  '));
        for (const el of [td, ...td.querySelectorAll('*')]) el.style.fontSize = '';
        let g2 = 0;
        while (rows(td) > MAX && g2++ < 40 && shrink(td)) {}
      }
    }
    if (rows(td) > MAX) over++;
  });
  return over;
}
"""

CSS = """
@page { size: 185mm 260mm; margin: 13mm 11mm; }
body { font-family: "PingFang SC", "Helvetica Neue", "Arial Unicode MS", sans-serif;
       font-size: 7pt; color: #222; line-height: 1.35; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 8px; color: #0b6fa4; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th { background: #e8f4fb; font-size: 6.8pt; padding: 2px 3px; text-align: left;
     border: 0.4px solid #a8cfe4; }
td { border: 0.4px solid #d8d8d8; padding: 1.6px 3px; vertical-align: top;
     word-wrap: break-word; }
tr { break-inside: avoid; page-break-inside: avoid; }
thead { display: table-header-group; }
b { color: #000; font-weight: bold; }
tr.sec td { background: #0b6fa4; color: #fff; font-size: 9pt; font-weight: bold;
            padding: 2px 4px; letter-spacing: 1px; }
/* 四列：习语 / 中文解释 / 常用·口语 / 例句 */
/* 列宽按各列实际内容量分配（平均半角宽 30 / 19 / 6 / 108），
   目标是四列都刚好两行、行高整齐。原来 21/17/55 的分法前两列大量留白，
   例句列却要挤三行、还被缩到 4pt */
th:nth-child(1), td:nth-child(1) { width: 17%; }
th:nth-child(2), td:nth-child(2) { width: 10%; }
th:nth-child(3), td:nth-child(3) { width: 9%; color: #d48806; font-size: 6pt;
                                   letter-spacing: -0.5px; white-space: nowrap; }
th:nth-child(4), td:nth-child(4) { width: 64%; color: #333; }
.lab { color: #999; font-size: 5.2pt; margin-right: 1px; }
"""


def md_to_html(md, title):
    body = re.search(r"<table>.*</table>", md, re.S)
    head = md.splitlines()[0].lstrip("# ").strip()
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title><style>{CSS}</style></head>"
            f"<body><h1>{head}</h1>{body.group(0) if body else ''}</body></html>")


def print_pdf(html_path, pdf_path):
    from playwright.sync_api import sync_playwright

    before = os.path.getmtime(pdf_path) if os.path.exists(pdf_path) else 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 609, "height": 1000})
        page.emulate_media(media="print")
        page.goto("file://" + html_path)
        over = page.evaluate(SHRINK_JS)
        page.pdf(path=pdf_path, print_background=True, **PAGE)
        browser.close()
    if not os.path.exists(pdf_path) or os.path.getmtime(pdf_path) <= before:
        raise RuntimeError("PDF 没有被写出来：" + pdf_path)
    print(f"实测仍超过两行的格子：{over} 个")


def add_bookmarks(path):
    """按条目首字母建书签，顺便清掉 Chrome 写进去的 UA/producer。"""
    import fitz

    doc = fitz.open(path)
    toc, seen = [], set()
    for i, page in enumerate(doc):
        # 只认渲染时插进去的分隔条：整段就一个大写字母，而且字号 9pt 明显比正文大。
        # 光看「整行是单个字母」不行，正文里 A、I 这类单字母条目会混进来（428 条书签）；
        # 也别拿每页第一行的首字母凑合——条目大多以 a/the/be 开头，排出来是乱序的
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    t = span["text"].strip()
                    if (len(t) == 1 and t.isascii() and t.isalpha()
                            and span["size"] > 8
                            and t.upper() not in seen):
                        seen.add(t.upper())
                        toc.append([1, t.upper(), i + 1])
    doc.set_toc(sorted(toc, key=lambda x: x[2]))
    doc.set_metadata({"title": "牛津习语词典", "producer": "", "creator": "",
                      "author": "", "subject": "", "keywords": ""})
    tmp = path + ".tmp"
    doc.save(tmp, garbage=4, deflate=True)
    n = len(doc)
    doc.close()
    os.replace(tmp, path)
    print(f"{n} 页，{os.path.getsize(path)/1024/1024:.0f} MB，书签 {len(toc)} 条")


def main():
    os.makedirs(PDF, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    md = open(os.path.join(OUT, "牛津习语词典.md")).read()
    if "--sample" in sys.argv:                # 只排前 200 条，用来看版式
        rows = re.findall(r"<tr>.*?</tr>", md, re.S)
        md = (md.split("<table>")[0] + "<table>" + rows[0]
              + "".join(rows[1:201]) + "</table>")
        name = "_sample"
    else:
        name = "牛津习语词典"
    html_path = os.path.join(WORK, f"{name}.html")
    open(html_path, "w").write(md_to_html(md, name))
    pdf_path = os.path.join(PDF, f"{name}.pdf")
    print_pdf(html_path, pdf_path)
    add_bookmarks(pdf_path)
    print(pdf_path)


if __name__ == "__main__":
    main()
