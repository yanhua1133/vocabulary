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


# 搭配里的占位词，例句里不会原样出现
SKIP = {"sb", "sth", "sb's", "sth's", "one's", "your", "a", "an", "the",
        "of", "to", "in", "on", "at", "for", "with", "and", "or", "etc"}


def bold_words(text, phrases):
    """例句里把这一格的搭配**整个**标粗，不是挑几个词。

    词形变化的后缀要给够：`clog` 在例句里是 `clogging`，只放 3 个字母的余量
    就匹配不上，那条搭配在例句里等于没标。
    """
    for p in phrases:
        for w in p.replace("/", " ").split():
            w = w.strip("()")
            if len(w) < 3 or w.lower() in SKIP:
                continue
            stem = w[:-1] if len(w) > 4 and w.endswith("e") else w
            text = re.sub(rf"(?<![>\w]){re.escape(stem)}(\w{{0,5}})(?!\w)",
                          rf"<b>{stem}\1</b>", text, flags=re.I)
    text = re.sub(r"<b>(<b>.*?</b>)</b>", r"\1", text)      # 别嵌套
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
    # 词头列**不能用 rowspan**：`system` 这种词条几百行，rowspan 一跨页，
    # Chrome 会把那一格的边框重画一遍，第一、二列之间冒出两条竖线，
    # 而且格子高度算错、竖线直接戳出表格底边。
    # 改成每行都出一个 td，空的那些去掉上边框——看着照样是合并的，还没有跨页毛病。
    for word, words, cn, ex in rows:
        head = (f'<td class="c1"><b>{word}</b></td>' if word
                else '<td class="c1 cont"></td>')
        # 每格都打上列号：排版脚本按 class 认列，不靠 td.cellIndex
        lines.append(f'<tr>{head}<td class="c2"><b>{words}</b></td>'
                     f'<td class="c3">{cn}</td><td class="c4">{ex}</td></tr>')
    lines.append("</table>\n")
    p = os.path.join(OUT, "牛津搭配词典.md")
    open(p, "w").write("\n".join(lines))
    print(f"{n_words} 个词头，{len(rows)} 行")
    print(p)


if __name__ == "__main__":
    main()
