"""Pass 17: 生成全量语义复核批次（机器查不出的那些错）。

Usage: 17_review_batches.py [批大小]
生成 work/batches/REV_NNN.json，每项是一个词的全部字段。
模型只回报**需要修正**的词，写入同名 .out.json，格式同 14_merge_cache.py。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BATCH = os.path.join(ROOT, "work", "batches")


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    words = json.load(open(os.path.join(DATA, "words.json")))
    book = json.load(open(os.path.join(DATA, "book.json")))

    ctx, order = {}, []
    for L in book["lists"]:
        for u in L["units"]:
            for e in u["entries"]:
                for w in [e["word"]] + e["syn"] + e["ant"]:
                    if w not in ctx:
                        ctx[w] = "" if w == e["word"] else e["word"]
                        order.append(w)

    items = []
    for w in order:
        r = words.get(w)
        if not r:
            continue
        items.append({
            "word": w, "ipa": r.get("ipa", ""), "cn": r.get("cn", ""),
            "pos": r.get("pos", ""), "phrase": r.get("phrase", ""),
            "phrase_cn": r.get("phrase_cn", ""), "example": r.get("example", ""),
            "spoken": r.get("spoken", 0), "related_to": ctx.get(w, ""),
        })

    os.makedirs(BATCH, exist_ok=True)
    # 只清输入批次，绝不删 .out.json（曾误删已完成的复核结果）
    for old in os.listdir(BATCH):
        if old.startswith("REV_") and not old.endswith(".out.json"):
            os.remove(os.path.join(BATCH, old))
    n = 0
    for i in range(0, len(items), size):
        p = os.path.join(BATCH, f"REV_{i//size:03d}.json")
        json.dump(items[i : i + size], open(p, "w"), ensure_ascii=False, indent=1)
        n += 1
    print(f"{len(items)} 个词 -> {n} 批")


if __name__ == "__main__":
    main()
