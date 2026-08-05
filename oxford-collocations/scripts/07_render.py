"""Pass 07: 渲染骨架版词表 → out/牛津搭配词典.md。

四列：**词头 / 义项 / 搭配类型 / 搭配内容**。搭配内容眼下是原书原文（搭配词、中文、
例句混在一起），下一步 `03_split.py` 会把它拆成「搭配词 / 中文 / 例句」三栏。

先出这版是为了能立刻打开看抽取质量，别等全套做完才发现前面抽错了。

Usage: 07_render.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")


def cell(s):
    return (s or "").replace("|", "／").replace("\n", " ").strip()


def main():
    book = json.load(open(os.path.join(DATA, "book.json")))
    rows = []
    for h in book:
        first_head = True
        for s in h["senses"]:
            first_sense = True
            for g in s["groups"]:
                rows.append((
                    f"{h['word']} <i>{h['pos']}</i>" if first_head else "",
                    cell(s["text"])[:40] if first_sense else "",
                    g["type"], cell(g["text"])))
                first_head = first_sense = False

    os.makedirs(OUT, exist_ok=True)
    words = sum(1 for r in rows if r[0])
    lines = ["# 牛津搭配词典\n",
             f"\n{words} 个词头，{len(rows)} 个搭配组。"
             "搭配内容目前是原书原文（搭配词、中文、例句混排），待拆分。\n",
             "\n<table>",
             "<thead><tr><th>词头</th><th>义项</th><th>类型</th>"
             "<th>搭配内容</th></tr></thead>"]
    for word, sense, typ, text in rows:
        w = f"<b>{word}</b>" if word else ""
        lines.append(f"<tr><td>{w}</td><td>{sense}</td>"
                     f"<td>{typ}</td><td>{text}</td></tr>")
    lines.append("</table>\n")
    p = os.path.join(OUT, "牛津搭配词典.md")
    open(p, "w").write("\n".join(lines))
    print(f"{words} 个词头，{len(rows)} 个搭配组")
    print(p)


if __name__ == "__main__":
    main()
