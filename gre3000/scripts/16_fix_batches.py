"""Pass 16: 把 data/audit.json 里的问题词切成批次，交模型修。

Usage: 16_fix_batches.py [批大小]
生成 work/batches/FIX_NNN.json，每项：
  {word, problems, ipa, cn, pos, phrase, phrase_cn, example, related_to}
模型写回同名 .out.json（格式同 14_merge_cache.py 可吃的结构）。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BATCH = os.path.join(ROOT, "work", "batches")
FIELD_OF = {
    "ex_missing": "example", "ex_word": "example", "ex_len": "example",
    "ex_frag": "example", "ex_glue": "example",
    "ph_word": "phrase", "ph_cn": "phrase_cn",
    "cn_missing": "cn", "cn_latin": "cn",
    "ipa_missing": "ipa", "ipa_bad": "ipa",
    "pos_missing": "pos", "pos_morph": "pos",
    "spell": "example",
}


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 55
    audit = json.load(open(os.path.join(DATA, "audit.json")))
    words = json.load(open(os.path.join(DATA, "words.json")))
    book = json.load(open(os.path.join(DATA, "book.json")))

    ctx = {}
    for L in book["lists"]:
        for u in L["units"]:
            for e in u["entries"]:
                for w in e["syn"] + e["ant"]:
                    ctx.setdefault(w, e["word"])

    items = []
    for w, probs in sorted(audit.items()):
        r = words.get(w)
        if not r:
            continue
        fix = sorted({FIELD_OF[p] for p in probs if p in FIELD_OF})
        if not fix:
            continue
        items.append({
            "word": w, "problems": probs, "fix": fix,
            "ipa": r.get("ipa", ""), "cn": r.get("cn", ""), "pos": r.get("pos", ""),
            "phrase": r.get("phrase", ""), "phrase_cn": r.get("phrase_cn", ""),
            "example": r.get("example", ""),
            "related_to": ctx.get(w, ""),
        })

    os.makedirs(BATCH, exist_ok=True)
    for old in os.listdir(BATCH):
        if old.startswith("FIX_"):
            os.remove(os.path.join(BATCH, old))
    n = 0
    for i in range(0, len(items), size):
        p = os.path.join(BATCH, f"FIX_{i//size:03d}.json")
        json.dump(items[i : i + size], open(p, "w"), ensure_ascii=False, indent=1)
        n += 1
    print(f"{len(items)} 个待修词 -> {n} 批")


if __name__ == "__main__":
    main()
