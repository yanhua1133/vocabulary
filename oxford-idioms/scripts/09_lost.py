"""Pass 09: 捞回被 OCR 粘进别人行里、又被子 agent 丢掉的习语 → work/lost.json。

原书两条习语被 OCR 挤进同一行时（`drive a hard ˈbargain what sb is ˈdriving at`），
子 agent 只会留下其中一条，另一条就整条消失了。

做法：拿原始行减去已收录的那条，剩下的部分如果自己带重音符号、词数像个习语、
而且全书别处也没有，就当成丢失的条目捞出来，交给模型补释义和例句。

Usage: 09_lost.py
"""
import importlib.util
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "work")

spec = importlib.util.spec_from_file_location("p07", os.path.join(HERE, "07_render.py"))
p07 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p07)

CJK = re.compile(r"[\u4e00-\u9fff]")
# 释义正文的痕迹：义项编号、词源框、整句英文
PROSE = re.compile(r"(ORIGIN|NOTE|\badj\b|\bnoun\b|\bverb\b|[0-9]|[a-z]\. |"
                   r"\b(is|are|was|were|means|used|when|because|that|which)\b)")


def key(s):
    return re.sub(r"[^a-z]", "", s.lower())


def main():
    book, cache = p07.load()
    flat = p07.build(book, cache)
    rows = p07.final_rows(book, cache)[0]
    have = {key(r[1]) for r in rows}

    out, seen = [], set()
    for hid, word, idiom, cn, ex, from_cache, raw, body in flat:
        a, b = key(idiom), key(raw)
        if not (a and a in b and len(b) - len(a) >= 12):
            continue
        rest = re.sub(re.escape(idiom.strip()), "", raw, flags=re.I).strip(" •◆-,;")
        k = key(rest)
        if len(k) < 10 or CJK.search(rest) or "ˈ" not in rest and "'" not in rest:
            continue
        if PROSE.search(rest) or not 2 <= len(rest.split()) <= 12:
            continue
        if k in have or k in seen or any(k in h for h in have):
            continue
        seen.add(k)
        out.append({"id": f"L{len(out)}", "w": word, "i": rest, "cn": ""})

    os.makedirs(WORK, exist_ok=True)
    json.dump(out, open(os.path.join(WORK, "lost.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"捞回 {len(out)} 条丢失的习语 → work/lost.json")
    for x in out[:12]:
        print(f"   {x['w']:14} | {x['i'][:52]}")


if __name__ == "__main__":
    main()
