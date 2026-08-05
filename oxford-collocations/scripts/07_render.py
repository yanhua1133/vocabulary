"""Pass 07: 渲染词表 → out/牛津搭配词典.md。

四列：**词头 / 搭配 / 中文 / 例句**。

搭配写完整形式（`hastily abandon`、`abandon sb to their fate`），不留原书那种
省略写法和 `~`；一个格子里放一条，多条就在格内换行。例句里把讨论的搭配标粗。

「类型」（ADJ./PREP./PHRASES）和「义项」两列去掉了——查搭配时用不上，白占地方。

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
    src = os.path.join(DATA, "expanded.json")
    book = json.load(open(src if os.path.exists(src)
                          else os.path.join(DATA, "book.json")))
    rows = []
    for h in book:
        first_head = True
        for s in h["senses"]:
            first_sense = True
            for g in s["groups"]:
                for sub in g.get("subs") or []:
                    full = sub.get("full") or []
                    if not full:
                        continue
                    ex = ""
                    for en, zh in (g.get("examples") or [])[:1]:
                        ex = f"{cell(en)}<br>{cell(zh)}"
                    rows.append((
                        f"{h['word']} <i>{h['pos']}</i>" if first_head else "",
                        "<br>".join(cell(x) for x in full),
                        cell(sub["cn"]), ex))
                    first_head = False

    os.makedirs(OUT, exist_ok=True)
    n_words = sum(1 for r in rows if r[0])

    lines = ["# 牛津搭配词典\n",
             f"\n{n_words} 个词头，{len(rows)} 行，"
             f"{sum(len(x.get('full') or []) for h in book for s in h['senses'] for g in s['groups'] for x in (g.get('subs') or []))} 条完整搭配。"
             "例句里加粗的是当前这条搭配。\n",
             "\n<table>",
             "<thead><tr><th>词头</th><th>搭配</th><th>中文</th>"
             "<th>例句</th></tr></thead>"]
    for word, words, cn, ex in rows:
        w = f"<b>{word}</b>" if word else ""
        lines.append(f"<tr><td>{w}</td><td><b>{words}</b></td>"
                     f"<td>{cn}</td><td>{ex}</td></tr>")
    lines.append("</table>\n")
    p = os.path.join(OUT, "牛津搭配词典.md")
    open(p, "w").write("\n".join(lines))
    print(f"{n_words} 个词头，{len(rows)} 行")
    print(p)


if __name__ == "__main__":
    main()
