"""Pass 07: 渲染词表 → out/牛津搭配词典.md。

四列：**词头 / 搭配 / 中文 / 例句**。

搭配写完整形式（`hastily abandon`、`abandon sb to their fate`），不留原书那种
省略写法和 `~`；一个格子里放一条，多条就在格内换行。例句里把讨论的搭配标粗。

「类型」（ADJ./PREP./PHRASES）和「义项」两列去掉了——查搭配时用不上，白占地方。

Usage: 07_render.py
"""
import importlib.util
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")


_spec = importlib.util.spec_from_file_location(
    "p04", os.path.join(os.path.dirname(os.path.abspath(__file__)), "04_expand.py"))
_p04 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p04)


def cell(s):
    return (s or "").replace("|", "／").replace("\n", " ").strip()


def bold_words(text, phrases):
    """例句里把整条搭配标粗，**连虚词一起**。

    先当成一个短语整体去找：`a matter of time`、`in the system` 要连 a / of / in / the
    一起标黑，只标实词的话中间夹着没加粗的虚词，看着像标漏了。
    词与词之间允许有屈折后缀和插入的修饰语。

    整条对不上（`clog system` 在例句里是 `clogging up the court system`）才退回
    逐词标，这时虚词就不标了——它们在句中位置对不上，标了反而误导。
    """
    for p in phrases:
        raw = [w.strip("()") for w in p.split()]
        raw = [w for w in raw if w and w.lower() not in PLACEHOLDER]
        if not raw:
            continue
        # `a/the` 是二选一，得转成正则的「或」；拆成两个词的话
        # `in a/the system` 就永远匹配不上例句里的 `in the system`
        parts = []
        for w in raw:
            alts = [x for x in w.split("/") if x]
            parts.append("(?:" + "|".join(re.escape(x) for x in alts) + ")"
                         if len(alts) > 1 else re.escape(alts[0]) if alts else "")
        parts = [x for x in parts if x]
        words = [x for w in raw for x in w.split("/") if x]
        # 整条短语：词之间允许屈折后缀，也允许插进一两个修饰语
        pat = r"\w{0,4}[\s,]+(?:\w+[\s,]+){0,2}".join(parts)
        # 前后要卡词边界，否则 `in` 会匹配到 `links` 里面去
        m = re.search(r"\b" + pat + r"\w{0,4}\b", text, flags=re.I)
        if m and "<b>" not in m.group(0):
            text = text[:m.start()] + f"<b>{m.group(0)}</b>" + text[m.end():]
            continue
        for w in words:                       # 整条对不上，逐词标实词
            if len(w) < 3 or w.lower() in FUNCTION:
                continue
            stem = w[:-1] if len(w) > 4 and w.endswith("e") else w
            text = re.sub(rf"(?<![>\w]){re.escape(stem)}(\w{{0,5}})(?!\w)",
                          rf"<b>{stem}\1</b>", text, flags=re.I)
    text = re.sub(r"<b>(<b>.*?</b>)</b>", r"\1", text)      # 别嵌套
    return re.sub(r"</b>([\s,]*)<b>", r"\1", text)


# 例句里不会原样出现的占位符
PLACEHOLDER = {"sb", "sth", "sb's", "sth's", "one's", "etc", "etc."}
# 逐词标时跳过的虚词——位置对不上，标了误导
FUNCTION = {"a", "an", "the", "of", "to", "in", "on", "at", "for", "with",
            "and", "or", "be", "your", "his", "her", "their", "its"}


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
                    key = h["word"] + "||" + re.sub(r"[^a-z]", "", full[0].lower())
                    if "!drop!" + key in cache:
                        continue          # 搭配被 OCR 毁得没法还原，整行不要
                    got = cache.get(key)
                    if got:
                        full = [_p04.fix_phrase(x) for x in (got.get("c") or full)]
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
             "<thead><tr><th>单词</th><th>搭配</th><th>解释</th>"
             "<th>例句</th></tr></thead>"]
    # 词头列**不能用 rowspan**：`system` 这种词条几百行，rowspan 一跨页，
    # Chrome 会把那一格的边框重画一遍，第一、二列之间冒出两条竖线，
    # 而且格子高度算错、竖线直接戳出表格底边。
    # 改成每行都出一个 td，空的那些去掉上边框——看着照样是合并的，还没有跨页毛病。
    for word, words, cn, ex in rows:
        head = (f'<td class="c1 newword"><b>{word}</b></td>' if word
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
