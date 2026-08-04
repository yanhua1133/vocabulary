"""Pass 18: 把 out/List<N>.md 转成 pdf/List<N>.pdf（16 开 185×260mm 竖版）。

md 里的表格本来就是内嵌 HTML，所以只需把标题行包成 HTML、套上打印样式，
再用无头 Chrome 打印（系统自带，中文与 IPA 字符都能正常渲染）。

Usage: 18_pdf.py [list numbers...]   (default: all)
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
PDF = os.path.join(ROOT, "pdf")
WORK = os.path.join(ROOT, "work", "html")
# 系统 Chrome 被企业策略禁掉了 headless 打印，改用 playwright 自带的 Chromium
PAGE = {"width": "185mm", "height": "260mm",
        "margin": {"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"}}


# 估算只能定初值，真实行数必须在浏览器里实测：超两行就按比例缩字号
SHRINK_JS = """
() => {
  const MIN = 4.2 * 96 / 72;
  let over = 0;
  // td.scrollHeight 是整行高度（由最高的格子决定），不能用来判断本格行数；
  // 用 Range 的行盒按 top 聚类，才是这一格自己占的行数。
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
    // 第一阶段：保持「英文一行 + 中文一行」，只缩字号
    let guard = 0;
    while (rows(td) > 2 && guard++ < 40 && shrink(td)) {}
    if (rows(td) > 2) {
      // 第二阶段：缩到下限还放不下，就改结构
      const l1 = td.querySelector('.l1'), l2 = td.querySelector('.l2');
      const ipa = td.querySelector('.ipa');
      if (l1 && l2) {
        // 短语/例句：把中文接到英文后面连排
        l1.style.display = 'inline';
        l2.style.display = 'inline';
        l1.insertAdjacentHTML('afterend', ' ');
      } else if (ipa) {
        // 第一列：多词条目的音标太长，丢掉音标保住「单词行 + 解释行」
        ipa.remove();
      }
      for (const el of [td, ...td.querySelectorAll('*')]) el.style.fontSize = '';
      let g2 = 0;
      while (rows(td) > 2 && g2++ < 40 && shrink(td)) {}
    }
    if (rows(td) > 2) {
      // 第三阶段：第一列的「单词行 + 解释行」也连排（多词条目太长时才会走到这）
      const nb = td.querySelectorAll('.nb');
      if (nb.length >= 2) {
        nb.forEach(x => x.style.display = 'inline');
        nb[0].insertAdjacentHTML('afterend', ' ');
        for (const el of [td, ...td.querySelectorAll('*')]) el.style.fontSize = '';
        let g3 = 0;
        while (rows(td) > 2 && g3++ < 40 && shrink(td)) {}
      }
    }
    if (rows(td) > 2) over++;
  });
  return over;
}
"""


def print_pdfs(jobs):
    """jobs: [(html_path, pdf_path)]，一次开一个浏览器全部打完。"""
    from playwright.sync_api import sync_playwright

    total = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # 关键：viewport 必须等于纸张可用宽度、并切到 print 媒体，否则 JS 量的是
        # 屏幕布局（默认 1280px），跟打印结果完全两样 —— 会误报「0 个超行」
        page = browser.new_page(viewport={"width": 609, "height": 1000})
        page.emulate_media(media="print")
        for html_path, pdf_path in jobs:
            page.goto("file://" + html_path)
            total += page.evaluate(SHRINK_JS)
            page.pdf(path=pdf_path, print_background=True, **PAGE)
            if not os.path.exists(pdf_path):
                raise RuntimeError("没有生成 " + pdf_path)
        browser.close()
    print(f"实测仍超过两行的格子：{total} 个")


CSS = """
/* 16 开（185×260mm），国内教辅/词汇书的常规开本 */
@page { size: 185mm 260mm; margin: 14mm 12mm 14mm 12mm; }
body { font-family: "PingFang SC", "Helvetica Neue", "Arial Unicode MS", sans-serif;
       font-size: 7pt; color: #222; line-height: 1.35; }
h1 { font-size: 15pt; margin: 0 0 6px; color: #0b6fa4; }
h2 { font-size: 10.5pt; margin: 11px 0 3px; color: #0b6fa4;
     border-bottom: 1.2px solid #0b6fa4; padding-bottom: 2px;
     break-after: avoid; page-break-after: avoid; }
table { width: 100%; border-collapse: collapse; margin-bottom: 8px;
        table-layout: fixed; }
th { background: #e8f4fb; font-size: 6.8pt; padding: 2px 3px; text-align: left;
     border: 0.4px solid #a8cfe4; }
td { border: 0.4px solid #d8d8d8; padding: 1.5px 3px; vertical-align: top;
     word-wrap: break-word; }
tr { break-inside: avoid; page-break-inside: avoid; }
/* 一个词的「词条行 + 例句行」在同一个 tbody 里，整组不许被分页切开 */
tbody { break-inside: avoid; page-break-inside: avoid; }
thead { display: table-header-group; }
td[colspan] { background: #fafafa; color: #444; font-size: 6.8pt; }
del { color: #999; }
b { color: #000; }
/* 4 列：单词·音标/词性·解释 / 常用+口语 / 常用短语 / 例句 */
th:nth-child(1), td:nth-child(1) { width: 20%; }
th:nth-child(2), td:nth-child(2) { width: 8%; color: #d48806; font-size: 6pt;
                                   letter-spacing: -0.4px; white-space: nowrap; }
th:nth-child(3), td:nth-child(3) { width: 20%; }
th:nth-child(4), td:nth-child(4) { width: 52%; color: #333; }
/* 片段的字号由 Python 按列宽估算，不裁字 */
.nb, .l1, .l2 { display: block; }
.l2 { color: #777; }
.w { font-weight: bold; }
.ipa { font-family: "Arial Unicode MS", serif; font-size: 0.92em; color: #666;
       margin-left: 3px; }
.pos { color: #0b6fa4; font-style: italic; margin-right: 3px; }
.lab { color: #999; font-size: 5.4pt; margin-right: 2px; }
.excn { color: #777; }
.rel { color: #999; font-weight: normal; font-size: 0.9em; margin-right: 2px; }
"""


PAGE_TEXT_PT = (185 - 24) / 25.4 * 72        # 版心宽度 161mm
COL_PT = {1: 0.20, 2: 0.08, 3: 0.20, 4: 0.52}
NARROW = set("iljtfrI.,;:'\u2019()[]/|! ")
WIDE = set("mwMW@%")
SAFE = 0.90                                  # 估算留出的余量


def text_em(t):
    """去掉标签后估算文本宽度，单位是「字号的倍数」。"""
    t = re.sub(r"<[^>]+>", "", t)
    em = 0.0
    for ch in t:
        o = ord(ch)
        if o > 0x2E80 or ch in "★☆—－":       # 汉字、全角标点、星号
            em += 1.0
        elif ch in NARROW:
            em += 0.34
        elif ch in WIDE:
            em += 0.92
        elif ch.isupper():
            em += 0.70
        else:
            em += 0.58
    return em


def tokens_em(text):
    """切成不可断开的最小单位：英文按空格分词，汉字每字可断。"""
    plain = re.sub(r"<[^>]+>", "", text)
    out = []
    for chunk in plain.split(" "):
        if not chunk:
            continue
        buf = ""
        for ch in chunk:
            if ord(ch) > 0x2E80:                 # 汉字/全角，可单独成行
                if buf:
                    out.append(text_em(buf))
                    buf = ""
                out.append(text_em(ch))
            else:
                buf += ch
        if buf:
            out.append(text_em(buf))
    return out


def wrapped_lines(toks, avail_pt, size_pt, space_em=0.32):
    """贪心模拟折行，返回实际行数。"""
    lines, cur = 1, 0.0
    for em in toks:
        w = em * size_pt
        add = w if cur == 0 else w + space_em * size_pt
        if cur + add > avail_pt and cur > 0:
            lines += 1
            cur = w
        else:
            cur += add
    return lines


def fit_wrap(text, base_pt, col, max_lines=2, floor_pt=4.4):
    """按真实折行结果定字号：逐步缩小直到排得进 max_lines 行。"""
    if not text.strip():
        return ""
    avail = PAGE_TEXT_PT * COL_PT[col] - 7
    toks = tokens_em(text)
    size = base_pt
    while size > floor_pt and wrapped_lines(toks, avail, size) > max_lines:
        size -= 0.15
    style = "" if size >= base_pt - 0.05 else f' style="font-size:{size:.2f}pt"'
    return f'<span class="fit2"{style}>{text}</span>'


def fit(text, base_pt, col, lines=1, floor_pt=4.6):
    """把片段压进指定行数：按列宽估算所需字号，超了就缩字号，绝不裁字。

    lines=1 禁止折行，用于逻辑上就该占一行的片段（单词+音标、词性+解释、搭配）。
    lines=2 允许自然折行，字号按两行总容量算，用于必然要折的例句。
    """
    if not text.strip():
        return ""
    avail = (PAGE_TEXT_PT * COL_PT[col] - 7) * lines
    em = text_em(text)
    if lines > 1:
        em += 4.0 * (lines - 1)      # 折行时行尾放不满，补上这部分损耗
    size = base_pt if em * base_pt <= avail * SAFE \
        else max(floor_pt, avail * SAFE / em)
    cls = "fit" if lines == 1 else "fit2"
    style = "" if size >= base_pt - 0.05 else f' style="font-size:{size:.2f}pt"'
    return f'<span class="{cls}"{style}>{text}</span>'


def drop_halfstar(html):
    """PDF 版丢掉常用度只有半颗星（☆）的近义词/反义词行；词头一律保留。"""
    dropped = 0

    def keep(m):
        nonlocal dropped
        block = m.group(0)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", block, re.S)
        if len(tds) >= 3 and tds[2].strip() == "☆" \
                and ("↳近" in tds[0] or "↳反" in tds[0]):
            dropped += 1
            return ""
        return block

    return re.sub(r"<tbody>.*?</tbody>", keep, html, flags=re.S), dropped


POS_EN = {"名词": "n.", "动词": "v.", "及物动词": "vt.", "不及物动词": "vi.",
          "形容词": "adj.", "副词": "adv.", "介词": "prep.", "连词": "conj.",
          "代词": "pron.", "数词": "num.", "冠词": "art.", "助动词": "aux.",
          "感叹词": "int."}


def to_four_columns(html):
    """PDF 版 4 列：第一格两行（单词+音标 / 词性+解释），例句并进同一行。"""
    def abbr(p):
        """短语列用词典缩写，别让 someone/something 白占宽度。"""
        p = re.sub(r"\bsomeone's\b", "sb.'s", p)
        p = re.sub(r"\bsomething's\b", "sth.'s", p)
        p = re.sub(r"\b(someone|somebody)\b", "sb.", p)
        p = re.sub(r"\bsomething\b", "sth.", p)
        return p

    def two_lines(en, cn_txt):
        """英文一行、中文一行。放不下时由 SHRINK_JS 退化成连排。"""
        if not en and not cn_txt:
            return ""
        out = f'<span class="l1">{en}</span>' if en else ""
        if cn_txt:
            out += f'<span class="l2">{cn_txt}</span>'
        return out

    def pos_en(cn):
        p = "/".join(POS_EN.get(x.strip(), x.strip())
                     for x in cn.split("、") if x.strip())
        return p.replace(".", "")             # adj./n. -> adj/n，省一格宽度

    def tighten(cn, budget_em):
        """解释太长时先精简内容，别一味缩字号。

        1) 删掉互为子串的冗余片段：「标准的；标准，规范」-> 「标准的；规范」
        2) 还超就去掉括号补充说明
        3) 还超就只留第一个义项
        """
        groups = [[x.strip() for x in g.split("，") if x.strip()]
                  for g in re.split(r"[；;]", cn) if g.strip()]
        flat = [x for g in groups for x in g]
        keep = [x for x in flat
                if not any(x != y and x in y for y in flat)]
        groups = [[x for x in g if x in keep] for g in groups]
        out = "；".join("，".join(g) for g in groups if g)

        if text_em(out) > budget_em:
            out = re.sub(r"（[^）]*）|\([^)]*\)", "", out).strip("；，")
        if text_em(out) > budget_em and "；" in out:
            out = out.split("；")[0]
        return out or cn

    def group(m):
        block = m.group(1)
        rows = re.findall(r"<tr>(.*?)</tr>", block, re.S)
        if not rows:
            return m.group(0)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", rows[0], re.S)
        if len(tds) != 7:
            return m.group(0)
        word, ipa, common, spoken, pos, cn, phrase = tds
        ex_en = ex_cn = ""
        if len(rows) > 1:
            got = re.findall(r"<td[^>]*>(.*?)</td>", rows[1], re.S)
            if got:
                ex = re.sub(r"^例\s*", "", got[0].strip())
                ex_en, _, ex_cn = ex.partition("  ")

        word = re.sub(r"</?del>", "", word)   # PDF 版第一列不打删除线
        word = word.replace("↳", "").strip()
        word = re.sub(r"^(近|反)\s*", r'<span class="rel">\1</span>', word)
        line1 = f'<span class="w">{word}</span>'
        if ipa.strip():
            line1 += f'<span class="ipa">{ipa}</span>'
        p = pos_en(pos)
        budget = (PAGE_TEXT_PT * COL_PT[1] - 7) / 7.0 - text_em(p) - 0.6
        line2 = (f'<span class="pos">{p}</span>' if p else "") + tighten(cn, budget)
        # 字号一律交给浏览器实测调整（见 SHRINK_JS），这里只组装内容
        c1 = f'<span class="nb">{line1}</span><span class="nb">{line2}</span>'

        c2 = (f'<span class="lab">常</span>{common}<br>'
              f'<span class="lab">口</span>{spoken}')

        ph = abbr(phrase).split("<br>")
        c3 = two_lines(ph[0], ph[1] if len(ph) > 1 else "")
        c4 = two_lines(ex_en, ex_cn.strip())
        cells = (c1, c2, c3, c4)
        return ("<tbody><tr>" + "".join(f"<td>{c}</td>" for c in cells)
                + "</tr></tbody>")

    html = re.sub(r"<tbody>(.*?)</tbody>", group, html, flags=re.S)
    return re.sub(r"<thead><tr>.*?</tr></thead>",
                  "<thead><tr><th>单词</th>"
                  "<th>常用 / 口语</th><th>常用短语</th><th>例句</th></tr></thead>",
                  html, flags=re.S)


def md_to_html(md, title):
    body = []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("## "):
            body.append(f"<h2>{s[3:]}</h2>")
        elif s.startswith("# "):
            body.append(f"<h1>{s[2:]}</h1>")
        else:
            body.append(line)
    html = "\n".join(body)
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
    html = re.sub(r"~~(.+?)~~", r"<del>\1</del>", html)
    html, dropped = drop_halfstar(html)
    html = to_four_columns(html)
    md_to_html.dropped = dropped
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title><style>{CSS}</style></head>"
            f"<body>{html}</body></html>")


def strip_metadata(path):
    """清掉 Chrome 写进去的 UA/producer 等信息，只留标题。"""
    import fitz

    if not os.path.exists(path):
        return
    doc = fitz.open(path)
    title = doc.metadata.get("title") or os.path.basename(path)[:-4]
    doc.set_metadata({"title": title, "producer": "", "creator": "",
                      "author": "", "subject": "", "keywords": ""})
    tmp = path + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, path)


def merge():
    """把 31 个分册合成一册，并建 List / Unit 两级书签。"""
    import fitz

    files = sorted((f for f in os.listdir(PDF) if re.fullmatch(r"List\d+\.pdf", f)),
                   key=lambda f: int(re.search(r"\d+", f).group()))
    book = fitz.open()
    toc = []
    for f in files:
        n = int(re.search(r"\d+", f).group())
        src = fitz.open(os.path.join(PDF, f))
        base = len(book)
        toc.append([1, f"List {n}", base + 1])
        seen = set()
        for i in range(len(src)):
            for u in re.findall(r"^Unit (\d+)$", src[i].get_text("text"), re.M):
                if u not in seen:
                    seen.add(u)
                    toc.append([2, f"Unit {u}", base + i + 1])
        book.insert_pdf(src)
        src.close()
        print(f"  合入 {f} ({len(book)} 页)")
    book.set_toc(toc)
    out = os.path.join(PDF, "GRE3000-合订本.pdf")
    book.set_metadata({"title": "GRE3000", "producer": "", "creator": "",
                       "author": "", "subject": "", "keywords": ""})
    book.save(out, garbage=4, deflate=True)
    print(f"\n{out}\n{len(book)} 页, {os.path.getsize(out)/1024/1024:.0f} MB, "
          f"书签 {len(toc)} 条")


def sample():
    """只排 List 1 Unit 1，用来看版式。"""
    md = open(os.path.join(OUT, "List1.md")).read()
    head, rest = md.split("## Unit", 1)
    unit1 = head + "## Unit" + rest.split("\n## Unit")[0]
    os.makedirs(PDF, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    h = os.path.join(WORK, "_sample.html")
    open(h, "w").write(md_to_html(unit1, "样张"))
    out = os.path.join(PDF, "_sample.pdf")
    print_pdfs([(h, out)])
    strip_metadata(out)
    print(out)


def main():
    if "--sample" in sys.argv:
        return sample()
    if "--merge" in sys.argv:
        return merge()
    wanted = {int(a) for a in sys.argv[1:] if a.isdigit()} or None
    os.makedirs(PDF, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    files = sorted((f for f in os.listdir(OUT) if re.fullmatch(r"List\d+\.md", f)),
                   key=lambda f: int(re.search(r"\d+", f).group()))
    done, jobs = [], []
    for f in files:
        n = int(re.search(r"\d+", f).group())
        if wanted and n not in wanted:
            continue
        html_path = os.path.join(WORK, f"List{n}.html")
        with open(html_path, "w") as fh:
            fh.write(md_to_html(open(os.path.join(OUT, f)).read(), f"List {n}"))
        pdf_path = os.path.join(PDF, f"List{n}.pdf")
        jobs.append((html_path, pdf_path))
        print(f"List{n}: 略去半星词 {md_to_html.dropped} 条")
        done.append(pdf_path)
    print_pdfs(jobs)
    for pdf_path in done:
        strip_metadata(pdf_path)
        print(f"{os.path.basename(pdf_path)}  "
              f"{os.path.getsize(pdf_path)/1024/1024:.1f} MB")
    print(f"\n{len(done)} 个 PDF 在 {PDF}/")


if __name__ == "__main__":
    main()
