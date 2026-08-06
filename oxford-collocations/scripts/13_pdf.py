"""Pass 13: 把 out/牛津搭配词典.md 排成 牛津搭配词典 重排版.pdf（16 开 185×260mm 竖版）。

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
FINAL = "牛津搭配词典 重排版.pdf"
PAGE = {"width": "185mm", "height": "260mm",
        "margin": {"top": "13mm", "bottom": "13mm", "left": "11mm",
                   "right": "11mm"}}

SHRINK_JS = """
() => {
  // 每列的字号下限分开定。习语列里有几十条带三四个变体的超长条目
  // （`get your ˈact together ◆ get sth/it toˈgether (informal) (also
  // get/have your ˈshit together)`），要压进两行只能让它比别处小得多；
  // 好在这些都是英文，小字比中文耐看。中文那两列绝不能低于 4.6pt
  // 按 class 取列号，不能用 td.cellIndex——有 rowspan 时它会左移一位
  const COL = (td) => "c1 c2 c3 c4".split(" ")
      .findIndex(c => td.classList.contains(c)) + 1 || 1;
  const MIN_BY_COL = [4.8, 5.4, 5.2, 5.0].map(x => x * 96 / 72);
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
    const MIN = MIN_BY_COL[COL(td) - 1];
    for (const el of [td, ...td.querySelectorAll('*')]) {
      const s = parseFloat(getComputedStyle(el).fontSize) * 0.93;
      if (s < MIN) return false;
      el.style.fontSize = s + 'px';
    }
    return true;
  };
  document.querySelectorAll('tbody td').forEach(td => {
    if (td.colSpan > 1) return;
    // 解释和例句一律压两行；搭配列例外，一格能有八九条，竖排本来就该占那么多行
    const MAX = [2, 14, 2, 2][COL(td) - 1];
    if (rows(td) <= MAX) return;

    // **先拆掉中英之间那个换行**，让中文接在英文后面连排——省下来的一整行
    // 往往就够了，不必动字号。先缩字号是本末倒置：
    // `under the new system, all children will be monitored by a social worker.`
    // 这种英文占满一行的，缩字号只会把整格都缩小，连排却能原样两行放下
    const br = td.querySelector('br');
    if (br) {
      br.replaceWith(document.createTextNode('  '));
      if (rows(td) <= MAX) return;
    }
    // 连排还放不下才缩字号
    let guard = 0;
    while (rows(td) > MAX && guard++ < 40 && shrink(td)) {}
    // 缩完再尽量涨回去：一步缩 7% 常常缩过头，字小得可怜宽度却剩一大截
    for (let g = 0; guard > 0 && g < 12; g++) {
      const els = [td, ...td.querySelectorAll('*')];
      const saved = els.map(el => getComputedStyle(el).fontSize);
      els.forEach((el, i) => { el.style.fontSize = parseFloat(saved[i]) * 1.03 + 'px'; });
      if (rows(td) > MAX) {
        els.forEach((el, i) => { el.style.fontSize = saved[i]; });
        break;
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
/* flex 布局下 border-collapse 不起作用，每格只画右边和下边，
   左边和上边由整张表的外框和上一行补 */
th { background: #e8f4fb; font-size: 6.8pt; padding: 2px 3px; text-align: left;
     border-right: 0.5pt solid #5a8fae; border-bottom: 0.5pt solid #5a8fae; }
td { border-right: 0.5pt solid #9a9a9a; border-bottom: 0.5pt solid #9a9a9a;
     padding: 1.6px 3px; word-wrap: break-word; overflow-wrap: break-word; }
th:first-child, td:first-child { border-left: 0.5pt solid #9a9a9a; }
thead tr { border-top: 0.5pt solid #5a8fae; }
tbody tr:first-child { border-top: 0.5pt solid #9a9a9a; }
/* 最右这条贴着版心边界，细线在阅读器里低缩放时会被丢掉。
   Chrome 打印时无论 border 写多粗都只画 0.75pt（collapse、separate、
   px、pt 全试过），所以改用背景渐变画这条线——背景不走 border 那套渲染 */
th:last-child, td:last-child {
  border-right: none;
  background-image: linear-gradient(to right, transparent calc(100% - 1.6pt),
                                    #444 calc(100% - 1.6pt));
}
th:last-child { background-color: #e8f4fb; }
/* **不用真表格布局**：Chrome 打印时不认 `tr` 上的 break-inside，
   行照样被分页拦腰切断，上半页留半句、下半页留半句。
   改成 flex 排出来的伪表格——每行是个 block 级的 flex 容器，
   block 元素的 break-inside Chrome 是认的。 */
table, thead, tbody { display: block; }
tr { display: flex; break-inside: avoid; page-break-inside: avoid; }
th, td { display: block; box-sizing: border-box; }
b { color: #000; font-weight: bold; }
tr.sec td { background: #0b6fa4; color: #fff; font-size: 9pt; font-weight: bold;
            padding: 2px 4px; letter-spacing: 1px; }
/* 四列：习语 / 中文解释 / 常用·口语 / 例句 */
/* 五列，按实测内容量分配（平均半角宽 3 / 6 / 7 / 75 / 285）。
   词头和义项列很多行是空的（同一词头/义项只在第一行写），但要留得下最宽的那些 */
/* 用 flex 简写一次写全，别让 `flex: 0 0 auto` 和 flex-basis 打架 */
th:nth-child(1), td:nth-child(1) { flex: 0 0 10%; }
th:nth-child(2), td:nth-child(2) { flex: 0 0 26%; }
th:nth-child(3), td:nth-child(3) { flex: 0 0 22%; color: #444; }
th:nth-child(4), td:nth-child(4) { flex: 0 0 42%; color: #333; }
.lab { color: #999; font-size: 5.2pt; margin-right: 1px; }
tr.newpage { break-before: page; page-break-before: always; }
/* 每页顶上重复的表头 */
tr.repeat-head > * { background: #e8f4fb; font-size: 6.8pt; font-weight: normal;
                     color: #222; border-right: 0.5pt solid #5a8fae;
                     border-bottom: 0.5pt solid #5a8fae; padding: 2px 3px; }
.nw { white-space: nowrap; }            /* 别在重音符号后面断行 */
/* 单词列要真的连成一片：border-collapse 下只去掉续行格的上边框没用，
   上一格的下边框还在，横线照样一条条画出来。得把这一列的横线全撤掉，
   再单独给「换了单词」的那一格补一条上边框 */
td.c1 { border-top: none; border-bottom: none; }
td.c1.newword { border-top: 0.5pt solid #9a9a9a; }
/* 每页最后一格、以及整张表的最后一格，都要把底边封上 */
td.c1.pageend, tbody tr:last-child > td.c1 {
  border-bottom: 0.5pt solid #9a9a9a; }
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


# 排完版之后再跑一遍：合并单元格跨页时，在新页顶上把单词重新写一遍。
# 纸面上看不到上一页，光靠 border 连一片的话，翻过来那页第一列就是空的
# 自己算分页，不指望 CSS。Chrome 打印时既不认表格行的 break-inside，
# JS 又量不出它把页切在哪儿——那就干脆自己按累计高度切，切完顺手把单词补上。
PAGINATE_JS = """
(pageH) => {
  const rows = [...document.querySelectorAll('tbody tr')];
  const head = document.querySelector('thead');
  const headH = head ? head.getBoundingClientRect().height : 0;
  const title = document.querySelector('h1');
  let acc = (title ? title.getBoundingClientRect().height + 8 : 0) + headH;
  let word = '', added = 0, prev = null;
  for (const tr of rows) {
    const c1 = tr.querySelector('td.c1');
    if (c1 && !c1.classList.contains('cont')) word = c1.innerHTML;
    let h = tr.getBoundingClientRect().height;
    if (acc + h > pageH) {                 // 这一行放不下了，从它开始翻页
      // 单词列整列没有横线，翻页时上一页最后一格就没了底边、开着口。
      // 给这一页的最后一行补一条
      if (prev) {
        const p1 = prev.querySelector('td.c1');
        if (p1) p1.classList.add('pageend');
      }
      tr.classList.add('newpage');
      // flex 布局下 thead 不会自动在每页重复，自己插一份
      if (head) {
        const clone = head.firstElementChild.cloneNode(true);
        clone.classList.add('repeat-head');
        tr.parentNode.insertBefore(clone, tr);
        clone.classList.add('newpage');
        tr.classList.remove('newpage');
      }
      acc = headH;
      if (c1 && c1.classList.contains('cont') && word) {
        c1.innerHTML = word;               // 新页第一行，把单词重写一遍
        c1.classList.remove('cont');
        c1.classList.add('newword');
        added++;
        h = tr.getBoundingClientRect().height;   // 补完字行可能变高，重量一次
      }
    }
    acc += h;
    prev = tr;
  }
  return added;
}
"""


def print_pdf(html_path, pdf_path):
    from playwright.sync_api import sync_playwright

    before = os.path.getmtime(pdf_path) if os.path.exists(pdf_path) else 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 609, "height": 1000})
        page.emulate_media(media="print")
        page.goto("file://" + html_path)
        over = page.evaluate(SHRINK_JS)
        # 正文区高度：纸高 260mm 减上下边距 26mm，留 4px 余量防止贴边溢出
        added = page.evaluate(PAGINATE_JS, (260 - 26) / 25.4 * 96 - 4)

        page.pdf(path=pdf_path, print_background=True, **PAGE)
        browser.close()
    if not os.path.exists(pdf_path) or os.path.getmtime(pdf_path) <= before:
        raise RuntimeError("PDF 没有被写出来：" + pdf_path)
    print(f"实测仍超过两行的格子：{over} 个；翻页处补写单词 {added} 次")


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
    md = open(os.environ.get("MD") or os.path.join(OUT, "牛津搭配词典.md")).read()
    if "--sample" in sys.argv:                # 看版式用的临时文件
        # 指定了 MD 就直接排它，别再切一遍——外面拼好的片段会被切没
        if not os.environ.get("MD"):
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
