"""Pass 07: 渲染词表 → out/牛津搭配词典.md。

五列：**词头 / 义项 / 类型 / 搭配词 / 中文**，例句附在中文后面。
一个搭配组一行，组里的小类用 `|` 隔开，跟原书的排法一致。

按小类逐行铺开会有 7.6 万行，太厚；按词头合并又太挤，所以折中按组。

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
    src = os.path.join(DATA, "groups.json")
    book = json.load(open(src if os.path.exists(src)
                          else os.path.join(DATA, "book.json")))
    rows = []
    for h in book:
        first_head = True
        for s in h["senses"]:
            first_sense = True
            for g in s["groups"]:
                subs = g.get("subs") or [{"words": g["text"], "cn": ""}]
                words = " | ".join(x["words"] for x in subs if x["words"])
                cn = " | ".join(x["cn"] for x in subs if x["cn"])
                for en, zh in (g.get("examples") or [])[:1]:
                    cn += f"<br><i>{cell(en)}</i> {cell(zh)}"
                rows.append((
                    f"{h['word']} <i>{h['pos']}</i>" if first_head else "",
                    cell(s["text"])[:40] if first_sense else "",
                    g["type"], cell(words), cn))
                first_head = first_sense = False

    os.makedirs(OUT, exist_ok=True)
    n_words = sum(1 for r in rows if r[0])
    n_subs = sum(len(g.get("subs") or [])
                 for h in book for s in h["senses"] for g in s["groups"])
    lines = ["# 牛津搭配词典\n",
             f"\n{n_words} 个词头，{len(rows)} 个搭配组，{n_subs} 个小类。\n",
             "\n<table>",
             "<thead><tr><th>词头</th><th>义项</th><th>类型</th>"
             "<th>搭配词</th><th>中文 / 例句</th></tr></thead>"]
    for word, sense, typ, words, cn in rows:
        w = f"<b>{word}</b>" if word else ""
        lines.append(f"<tr><td>{w}</td><td>{sense}</td><td>{typ}</td>"
                     f"<td>{words}</td><td>{cn}</td></tr>")
    lines.append("</table>\n")
    p = os.path.join(OUT, "牛津搭配词典.md")
    open(p, "w").write("\n".join(lines))
    print(f"{n_words} 个词头，{len(rows)} 个搭配组，{n_subs} 个小类")
    print(p)


if __name__ == "__main__":
    main()
