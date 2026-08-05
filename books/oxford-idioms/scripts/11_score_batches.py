"""Pass 11: 切出给习语打分的批次 → work/scores/。

要打两个分：**常用程度**（这条习语在当代英语里有多常见）和**口语化程度**
（多大程度上属于口头表达而非书面语）。

跟 GRE3000 不同，这里没法用 wordfreq 客观算——wordfreq 只有单词频率，
习语是多词组合，查不到。只能交给模型判断，但把判断依据写死在提示里，
让不同批次之间的尺度尽量一致。

对应关系用**条目文本的归一化形式**做 key，不用行号：成品的行会随着去重、
改挂而变动，行号对不上，文本 key 稳定。

Usage: 11_score_batches.py [每批条数]   (默认 60)
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "work", "scores")

spec = importlib.util.spec_from_file_location("p07", os.path.join(HERE, "07_render.py"))
p07 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p07)


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    book, cache = p07.load()
    rows = p07.final_rows(book, cache)[0]
    rows = [list(r) for r in rows]
    rows = p07.with_book_examples(rows)[0]
    rows = p07.regroup(rows)[0]
    rows = p07.append_lost(rows)[0]

    items, seen = [], set()
    for r in rows:
        k = re.sub(r"[^a-z]", "", r[1].lower())
        if not k or k in seen:
            continue
        seen.add(k)
        items.append({"k": k, "i": r[1], "cn": r[2]})

    os.makedirs(WORK, exist_ok=True)
    for f in os.listdir(WORK):
        os.remove(os.path.join(WORK, f))
    n = 0
    for start in range(0, len(items), size):
        n += 1
        with open(os.path.join(WORK, f"s{n:03d}.json"), "w") as fh:
            json.dump(items[start:start + size], fh, ensure_ascii=False)
    print(f"{len(items)} 条 → {n} 个批次，每批 {size} 条，在 {WORK}/")


if __name__ == "__main__":
    main()
