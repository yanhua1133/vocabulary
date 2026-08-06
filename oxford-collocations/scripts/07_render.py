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


def bold_words(text, phrases):
    """例句里把这一格的搭配标粗。"""
    for p in phrases:
        for w in p.split():
            if len(w) < 4:
                continue
            text = re.sub(rf"(?<![>\w]){re.escape(w)}(\w{{0,3}})(?!\w)",
                          rf"<b>{w}\1</b>", text, count=1, flags=re.I)
    return re.sub(r"</b>(\s*)<b>", r"\1", text)


def main():
    src = os.path.join(DATA, "expanded.json")
    book = json.load(open(src if os.path.exists(src)
                          else os.path.join(DATA, "book.json")))
    cache_path = os.path.join(DATA, "cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}

    rows, fixed = [], 0
    for h in book:
        first_head = True
        for s in h["senses"]:
            for g in s["groups"]:
                for sub in g.get("subs") or []:
                    full = sub.get("full") or []
                    if not full:
                        continue
                    # 校对过的优先——OCR 抽出来的解释常带错字和串行，例句还缺七成
                    got = cache.get(h["word"] + "||" +
                                    re.sub(r"[^a-z]", "", full[0].lower()))
                    if got:
                        fixed += 1
                        cn = got["cn"]
                        en, _, zh = got["ex"].partition("  ")
                        ex = f"{cell(bold_words(en, full))}<br>{cell(zh)}"
                    else:
                        cn = cell(sub["cn"])
                        ex = ""
                        for en, zh in (sub.get("ex") or [])[:1]:
                            ex = f"{cell(en)}<br>{cell(zh)}" if zh else cell(en)
                    rows.append((
                        f"{h['word']} <i>{h['pos']}</i>" if first_head else "",
                        "<br>".join(cell(x) for x in full), cn, ex))
                    first_head = False

    os.makedirs(OUT, exist_ok=True)
    n_words = sum(1 for r in rows if r[0])

    lines = ["# 牛津搭配词典\n",
             f"\n{n_words} 个词头，{len(rows)} 行，"
             f"{sum(len(x.get('full') or []) for h in book for s in h['senses'] for g in s['groups'] for x in (g.get('subs') or []))} 条完整搭配。"
             f"其中 {fixed} 行的解释和例句经过校对。例句里加粗的是当前这条搭配。\n",
             "\n<table>",
             "<thead><tr><th>词头</th><th>搭配</th><th>解释</th>"
             "<th>例句</th></tr></thead>"]
    # 词头列合并单元格：同一个词头底下有多少行就跨多少行，
    # 不然那一列全是空格子，看着像散的
    spans, i = {}, 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and not rows[j][0]:
            j += 1
        spans[i] = j - i
        i = j
    for k, (word, words, cn, ex) in enumerate(rows):
        head = (f'<td rowspan="{spans[k]}"><b>{word}</b></td>'
                if k in spans else "")
        lines.append(f"<tr>{head}<td><b>{words}</b></td>"
                     f"<td>{cn}</td><td>{ex}</td></tr>")
    lines.append("</table>\n")
    p = os.path.join(OUT, "牛津搭配词典.md")
    open(p, "w").write("\n".join(lines))
    print(f"{n_words} 个词头，{len(rows)} 行")
    print(p)


if __name__ == "__main__":
    main()
