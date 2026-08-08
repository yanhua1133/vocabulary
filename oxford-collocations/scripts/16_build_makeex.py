#!/usr/bin/env python3
"""把手写的例句行文件 work/makeex/NNNN.txt 合成 work/makeex/NNNN.out.json。

每行格式： 英文 ||| 中译
行数必须和 NNNN.json 的条数一致，按顺序一一对应。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "work" / "makeex"


def stem(w):
    w = w.lower()
    if len(w) > 5:
        return w[: len(w) - 2]
    if len(w) > 3:
        return w[: len(w) - 1]
    return w


def has_coll(en, coll):
    coll = re.sub(r"\([^)]*\)", " ", coll)
    toks = [t for t in re.findall(r"[a-zA-Z']+", coll)]
    low = en.lower()
    miss = []
    for t in toks:
        if len(t) <= 2:
            continue
        if stem(t) not in low:
            miss.append(t)
    return miss


def main(tag):
    src = json.load(open(D / f"{tag}.json"))
    lines = [l for l in (D / f"{tag}.txt").read_text().split("\n") if l.strip()]
    if len(lines) != len(src):
        sys.exit(f"[{tag}] 行数 {len(lines)} != 条数 {len(src)}")
    ex = []
    bad_words, bad_coll, bad_zh = [], [], []
    for i, (item, line) in enumerate(zip(src, lines)):
        if "|||" not in line:
            sys.exit(f"[{tag}] 第 {i+1} 行没有分隔符: {line[:60]}")
        en, zh = [x.strip() for x in line.split("|||", 1)]
        n = len(en.split())
        if n < 9 or n > 19:
            bad_words.append((i + 1, n, en))
        miss = has_coll(en, item["coll"][0])
        if miss:
            bad_coll.append((i + 1, item["coll"][0], miss, en))
        if not zh or not zh.endswith(("。", "！", "？")):
            bad_zh.append((i + 1, zh))
        ex.append({"k": item["k"], "en": en, "zh": zh})
    out = {"n": len(ex), "ex": ex}
    (D / f"{tag}.out.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[{tag}] 写出 {len(ex)} 条")
    for name, lst in (("词数", bad_words), ("缺搭配", bad_coll), ("中译", bad_zh)):
        if lst:
            print(f"  {name}问题 {len(lst)}:")
            for row in lst[:40]:
                print("   ", row)


if __name__ == "__main__":
    main(sys.argv[1])
