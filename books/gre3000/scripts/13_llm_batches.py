"""Pass 13: emit batch files of words still missing model-written columns.

Usage: 13_llm_batches.py <list number> [batch size]
Writes work/batches/L<N>_<i>.json - each a list of
  {word, pos, cn, related_to, need:[fields]}
An agent fills work/batches/L<N>_<i>.out.json with
  {word: {cn, pos, phrase, example, spoken}}
then 14_merge_cache.py folds it into data/enrich_cache.json.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BATCH = os.path.join(ROOT, "work", "batches")


def main():
    lst = sys.argv[1]                      # 数字 = 单个 List；"all" = 全书剩余
    lst = int(lst) if lst != "all" else "all"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    book = json.load(open(os.path.join(DATA, "book.json")))
    words = json.load(open(os.path.join(DATA, "words.json")))

    ctx = {}
    order = []
    for L in book["lists"]:
        if lst != "all" and L["list"] != lst:
            continue
        for u in L["units"]:
            for e in u["entries"]:
                head = e["word"]
                for w in [head] + e["syn"] + e["ant"]:
                    if w not in ctx:
                        ctx[w] = head
                        order.append(w)

    items = []
    for w in order:
        r = words.get(w)
        if not r:
            continue
        need = [f for f in ("ipa", "cn", "pos", "phrase", "phrase_cn", "example")
                if not r.get(f)]
        if not need:
            continue
        items.append({"word": w, "pos": r.get("pos", ""), "cn": r.get("cn", ""),
                      "phrase": r.get("phrase", ""),
                      "related_to": ctx[w] if ctx[w] != w else "",
                      "need": need})

    os.makedirs(BATCH, exist_ok=True)
    tag = "ALL" if lst == "all" else str(lst)
    for old in os.listdir(BATCH):
        if old.startswith(f"L{tag}_"):
            os.remove(os.path.join(BATCH, old))
    n = 0
    for i in range(0, len(items), size):
        p = os.path.join(BATCH, f"L{tag}_{i//size:03d}.json")
        json.dump(items[i : i + size], open(p, "w"), ensure_ascii=False, indent=1)
        n += 1
    print(f"list {lst}: {len(items)} words needing fields -> {n} batches in {BATCH}")


if __name__ == "__main__":
    main()
