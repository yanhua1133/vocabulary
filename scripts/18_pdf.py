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
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

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
/* 列宽：单词 音标 常用 口语 词性 释义 短语 */
th:nth-child(1), td:nth-child(1) { width: 13%; }
th:nth-child(2), td:nth-child(2) { width: 14%; font-family: "Arial Unicode MS", serif; }
th:nth-child(3), td:nth-child(3),
th:nth-child(4), td:nth-child(4) { width: 7%; color: #d48806; font-size: 6pt;
                                   letter-spacing: -0.3px; }
th:nth-child(5), td:nth-child(5) { width: 11%; font-size: 6.4pt; }
th:nth-child(6), td:nth-child(6) { width: 22%; }
th:nth-child(7), td:nth-child(7) { width: 22%; }
"""


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


def main():
    if "--merge" in sys.argv:
        return merge()
    wanted = {int(a) for a in sys.argv[1:] if a.isdigit()} or None
    os.makedirs(PDF, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    files = sorted((f for f in os.listdir(OUT) if re.fullmatch(r"List\d+\.md", f)),
                   key=lambda f: int(re.search(r"\d+", f).group()))
    done = []
    for f in files:
        n = int(re.search(r"\d+", f).group())
        if wanted and n not in wanted:
            continue
        html_path = os.path.join(WORK, f"List{n}.html")
        with open(html_path, "w") as fh:
            fh.write(md_to_html(open(os.path.join(OUT, f)).read(), f"List {n}"))
        pdf_path = os.path.join(PDF, f"List{n}.pdf")
        subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf_path}", f"file://{html_path}"],
            capture_output=True, timeout=600,
        )
        strip_metadata(pdf_path)
        size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
        print(f"List{n}.pdf  {size/1024/1024:.1f} MB  "
              f"（略去半星词 {md_to_html.dropped} 条）")
        done.append(pdf_path)
    print(f"\n{len(done)} 个 PDF 在 {PDF}/")


if __name__ == "__main__":
    main()
