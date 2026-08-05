"""Pass 12: render out/List<N>.md from book.json + words.json.

Each Unit is one table of 7 columns; the example sentence gets its own
full-width row underneath the word (an HTML colspan, since Markdown tables
cannot merge cells), which keeps the word rows short.  每个词的两行装在自己的
<tbody> 里，打印时才不会被分页切开。

Usage: 12_render.py [list numbers...]   (default: all)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")
COLS = ["单词", "音标", "常用", "口语", "词性", "中文释义", "常用短语"]
POS_CN = {
    "n": "名词", "v": "动词", "vt": "及物动词", "vi": "不及物动词",
    "adj": "形容词", "adv": "副词", "prep": "介词", "conj": "连词",
    "pron": "代词", "num": "数词", "art": "冠词", "aux": "助动词",
    "int": "感叹词", "interj": "感叹词",
}


def pos_cn(pos):
    out = []
    for part in (pos or "").split("/"):
        key = part.strip().rstrip(".").lower()
        if key:
            out.append(POS_CN.get(key, part.strip()))
    return "、".join(dict.fromkeys(out))


def stars(n):
    """★ = 一颗，☆ = 半颗。最低分就是半颗星（☆），没有零分。"""
    try:
        v = round(float(n) * 2) / 2
    except (TypeError, ValueError):
        v = 0.5
    v = max(0.5, min(5.0, v))
    full = int(v)
    return "★" * full + ("☆" if v - full >= 0.5 else "")


def cell(s):
    return (s or "").replace("\n", " ").strip()


def phrase_cell(rec):
    en = (rec.get("phrase") or "").strip()
    cn = (rec.get("phrase_cn") or "").strip()
    return f"{en}<br>{cn}" if en and cn else en or cn


def word_row(word, rec, prefix=""):
    name = f"<b>{cell(word)}</b>" if not prefix else f"{prefix} {cell(word)}"
    if rec.get("rare"):
        name = f"<del>{name}</del>"
    cells = [
        name,
        cell(rec.get("ipa") and f"/{rec['ipa']}/" or ""),
        stars(rec.get("common", 0)),
        stars(rec.get("spoken", 0)),
        cell(pos_cn(rec.get("pos", ""))),
        cell(rec.get("cn", "")),
        phrase_cell(rec),
    ]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def plan_dedup(book):
    """全书去重：每个单词整本书只出现一次。

    词头行一律保留（原书结构，含 5 个原书自带的重复词头）。近/反义词行在两种
    情况下略去：它本身就是书里的某个词头（那里有它的完整条目），或它在本书更早
    的位置已经出现过。返回允许输出的 (list, unit, 词条序号, 小写词) 集合。
    """
    heads = {e["word"].strip().lower()
             for L in book["lists"] for u in L["units"] for e in u["entries"]}
    seen, keep = set(), set()
    for L in book["lists"]:
        for u in L["units"]:
            for i, e in enumerate(u["entries"]):
                w = e["word"].strip().lower()
                keep.add((L["list"], u["unit"], i, w))
                seen.add(w)
                for x in e["syn"] + e["ant"]:
                    k = x.strip().lower()
                    if not k or k in heads or k in seen:
                        continue
                    seen.add(k)
                    keep.add((L["list"], u["unit"], i, k))
    return keep


def render_unit(lst, unit, words, keep):
    out = [f"\n## Unit {unit['unit']}\n", "<table>", "<thead><tr>"]
    out += [f"<th>{c}</th>" for c in COLS]
    out.append("</tr></thead>")
    for i, e in enumerate(unit["entries"]):
        rows = ([(e["word"], "")] + [(x, "↳近") for x in e["syn"]]
                + [(x, "↳反") for x in e["ant"]])
        for w, prefix in rows:
            token = (lst, unit["unit"], i, w.strip().lower())
            if token not in keep:
                continue
            keep.discard(token)          # 令牌用掉，同一词条里重复列的也只出一次
            rec = words.get(w, {})
            # 一个词的两行必须同页，所以各自单独成组
            out.append("<tbody>")
            out.append(word_row(w, rec, prefix))
            ex = cell(rec.get("example", ""))
            if ex:
                out.append(f'<tr><td colspan="{len(COLS)}">例 {ex}</td></tr>')
            out.append("</tbody>")
    out.append("</table>\n")
    return "\n".join(out)


def main():
    book = json.load(open(os.path.join(DATA, "book.json")))
    words = json.load(open(os.path.join(DATA, "words.json")))
    wanted = {int(a) for a in sys.argv[1:] if a.isdigit()} or None
    os.makedirs(OUT, exist_ok=True)
    # 去重是全书范围的，必须先按全书顺序算好，只渲染部分 List 时结果才一致
    keep = plan_dedup(book)
    for L in book["lists"]:
        if wanted and L["list"] not in wanted:
            continue
        parts = [f"# List {L['list']}\n"]
        parts += [render_unit(L["list"], u, words, keep) for u in L["units"]]
        p = os.path.join(OUT, f"List{L['list']}.md")
        open(p, "w").write("".join(parts))
        print(p)


if __name__ == "__main__":
    main()
