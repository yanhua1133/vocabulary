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
# 成品直接放在书目录顶层，名字带「重排版」跟同目录的原书区分开——
# 埋在 pdf/ 子目录里、又跟原书同名，找起来太费劲
PDF = ROOT
WORK = os.path.join(ROOT, "work", "html")
FINAL = "牛津习语词典 重排版.pdf"
PAGE = {"width": "185mm", "height": "260mm",
        "margin": {"top": "13mm", "bottom": "13mm", "left": "11mm",
                   "right": "11mm"}}

SHRINK_JS = """
() => {
  // 字号只允许取这几档，不做连续缩放。
  // 老做法是「每次缩 7%、再每次涨回 3%」，最后落在 0.93^n × 1.03^m 上，
  // 一页里能冒出二十几种字号（3.3pt 到 9.0pt），相邻两行大小不一，看着就是脏。
  // 改成固定档位后同一页最多五种字号，而且档与档之间差得够明显、不会像没对齐。
  const STEPS = [7.0, 6.4, 5.8, 5.2, 4.6, 4.0, 3.4, 2.9];
  // 每列能降到第几档。中文两列绝不能太小；习语列有几十条带三四个变体的超长条目
  // （`get your ˈact together ◆ get sth/it toˈgether (informal) (also
  // get/have your ˈshit together)`），只能让它一路降到底——好在都是英文，比中文耐看
  const FLOOR = [2.9, 4.6, 4.6, 4.6];
  const over = [];
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
  document.querySelectorAll('tbody td').forEach(td => {
    if (td.colSpan > 1) return;               // 字母分隔行
    const MAX = 2;                            // 四列一律两行，不许出现第三行
    // 例句列：英文一行、中文一行本来就放得下的，原样不动。
    // 只有放不下的才拆掉 <br> 让中英文连排——那个 <br> 会把格子钉死成两行，
    // 逼着英文缩字号硬挤进第一行，中文那行却空掉大半；连排后英文能用大字号
    // 溢到第二行、中文接着排，两行都填满
    if (td.cellIndex === 3 && rows(td) > MAX) {
      const br = td.querySelector('br');
      if (br) br.replaceWith(document.createTextNode('\\u2003\\u2003'));
    }
    if (rows(td) <= MAX) return;              // 八成的格子本来就放得下
    // 从大到小挑第一个放得下的档位。子元素的字号全用 em 写，跟着 td 一起缩，
    // 不用逐个 querySelectorAll 去改（那样会把 em 关系压平）
    const floor = FLOOR[td.cellIndex];
    for (const pt of STEPS) {
      if (pt > 7.0 || pt < floor) continue;
      td.style.fontSize = pt + 'pt';
      if (rows(td) <= MAX) return;
    }
    over.push(td.cellIndex + '列 ' + td.textContent.slice(0, 40));
  });
  return over;
}
"""

CSS = """
@page { size: 185mm 260mm; margin: 13mm 11mm; }
body { font-family: "PingFang SC", "Helvetica Neue", "Arial Unicode MS", sans-serif;
       font-size: 7pt; color: #222; line-height: 1.35; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 8px; color: #0b6fa4; }
/* 线要画得住：0.4px 的浅灰线在 300dpi 下只有一个像素多点，印出来几乎看不见，
   最右那条贴着版心边界的更是像没画。加粗到 0.6px 并压深颜色 */
/* 线要画得住：细线在不少 PDF 阅读器里低缩放时会被丢掉，最右那条贴着版心
   边界的尤其容易「消失」。所以外框 1.5px、格线 0.8px，颜色也压深；
   最右一列再显式指定一次 border-right，不指望 border-collapse 兜底 */
/* 用 separate 而不是 collapse：collapse 模式下 Chrome 打印时会把所有边框
   压成 0.75pt，想让某条线粗一点根本改不动（试过 1.5px、1.2pt 都没用）。
   separate + border-spacing:0 看起来一样，但每条边框的宽度是各画各的。
   也别拿外层 div 画外框——div 高度跟表格对不齐，竖边会甩到表格外面去。
   每格只画右边和下边，左边和上边由表格自己补，才不会画重。 */
table { width: 100%; border-collapse: separate; border-spacing: 0;
        table-layout: fixed; }
th { background: #e8f4fb; font-size: 6.8pt; padding: 2px 3px; text-align: left;
     border-right: 0.5pt solid #5a8fae; border-bottom: 0.5pt solid #5a8fae;
     border-top: 0.5pt solid #5a8fae; }
th:first-child { border-left: 0.5pt solid #5a8fae; }
td { border-right: 0.5pt solid #9a9a9a; border-bottom: 0.5pt solid #9a9a9a;
     padding: 1.6px 3px; vertical-align: top; word-wrap: break-word; }
td:first-child { border-left: 0.5pt solid #9a9a9a; }
/* 最右这条贴着版心边界，细线在阅读器里低缩放时会被丢掉。
   Chrome 打印时无论 border 写多粗都只画 0.75pt（collapse、separate、
   px、pt 全试过），所以改用背景渐变画这条线——背景不走 border 那套渲染 */
th:last-child, td:last-child {
  border-right: none;
  background-image: linear-gradient(to right, transparent calc(100% - 1.6pt),
                                    #444 calc(100% - 1.6pt));
}
th:last-child { background-color: #e8f4fb; }
tr { break-inside: avoid; page-break-inside: avoid; }
thead { display: table-header-group; }
b { color: #000; font-weight: bold; }
tr.sec td { background: #0b6fa4; color: #fff; font-size: 9pt; font-weight: bold;
            padding: 2px 4px; letter-spacing: 1px; }
/* 四列：习语 / 中文解释 / 常用·口语 / 例句 */
/* 列宽按各列内容宽度的 **P90** 分配，不是按平均值——目标是「九成的格子刚好两行满」。
   实测半角宽 P90 是 46 / 26 / 12 / 136，扣掉星级列固定要的宽度后按这个比例分。
   按平均值分会让长尾大量超行、被迫缩字号；这正是上一版一页里蹦出二十几种字号的原因。
   中文解释列从 10.5% 调到 11.5%：算宽度时忘了左右各 3px 的 padding，
   19 字以上的长释义在 4.6pt 下面差半个字放不下，全书有 9 条 */
th:nth-child(1), td:nth-child(1) { width: 19%; }
th:nth-child(2), td:nth-child(2) { width: 11.5%; }
/* 星级列 nowrap 是为了不让星号断行，那它就必须留够宽度——
   宽度不够时 nowrap 会把整张表撑破，最后一列被顶出纸面 */
th:nth-child(3), td:nth-child(3) { width: 10.5%; color: #d48806; font-size: 0.86em;
                                   letter-spacing: -0.4px; white-space: nowrap; }
th:nth-child(4), td:nth-child(4) { width: 59%; color: #333; }
/* 格子里的字号一律用 em：13_pdf.py 缩排时只改 td 一个值，子元素跟着一起缩。
   写成绝对 pt 的话，缩完子元素还是原大小，比正文还大 */
.lab { color: #999; font-size: 0.74em; margin-right: 1px; }
.nw { white-space: nowrap; }            /* 别在重音符号后面断行 */
/* 语域标签是次要信息，缩小它好把长条目压进两行 */
.tag { font-size: 0.72em; color: #777; font-weight: normal; }
"""


def md_to_html(md, title):
    body = re.search(r"<table>.*</table>", md, re.S)
    head = md.splitlines()[0].lstrip("# ").strip()
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title><style>{CSS}</style></head>"
            f"<body><h1>{head}</h1>"
            f"{body.group(0) if body else ''}</body></html>")


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
    print(f"实测仍超过两行的格子：{len(over)} 个")
    for x in over[:12]:
        print(f"      {x}")


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
    if "--sample" in sys.argv:                # 只排前 200 条，用来看版式（临时文件）
        rows = re.findall(r"<tr>.*?</tr>", md, re.S)
        md = (md.split("<table>")[0] + "<table>" + rows[0]
              + "".join(rows[1:201]) + "</table>")
        name = "_sample"
    else:
        name = FINAL[:-4]
    html_path = os.path.join(WORK, f"{name}.html")
    open(html_path, "w").write(md_to_html(md, name))
    pdf_path = os.path.join(PDF, f"{name}.pdf")
    print_pdf(html_path, pdf_path)
    add_bookmarks(pdf_path)
    print(pdf_path)


if __name__ == "__main__":
    main()
