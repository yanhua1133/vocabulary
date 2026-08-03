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


def render_unit(unit, words):
    out = [f"\n## Unit {unit['unit']}\n", "<table>", "<thead><tr>"]
    out += [f"<th>{c}</th>" for c in COLS]
    out.append("</tr></thead>")
    for e in unit["entries"]:
        seen = set()
        rows = ([(e["word"], "")] + [(x, "↳近") for x in e["syn"]]
                + [(x, "↳反") for x in e["ant"]])
        for w, prefix in rows:
            if w.lower() in seen:
                continue
            seen.add(w.lower())
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
    for L in book["lists"]:
        if wanted and L["list"] not in wanted:
            continue
        parts = [f"# List {L['list']}\n"]
        parts += [render_unit(u, words) for u in L["units"]]
        p = os.path.join(OUT, f"List{L['list']}.md")
        open(p, "w").write("".join(parts))
        print(p)


if __name__ == "__main__":
    main()
