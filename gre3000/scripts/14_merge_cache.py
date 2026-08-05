"""Pass 14: fold agent batch outputs into data/enrich_cache.json.

Usage: 14_merge_cache.py [glob-ish prefix, default all *.out.json]
Validates each record before accepting it so a bad batch cannot poison the cache.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BATCH = os.path.join(ROOT, "work", "batches")
FIELDS = ("ipa", "cn", "pos", "phrase", "phrase_cn", "example", "spoken")
IPA_OK = set("ˈˌːˑaɑɒæʌeɛɜəɪiɔoʊuʏyʍbdfɡghjklmnprstvwzʃʒθðŋɹɾɫʔ() .-")
POS_OK = re.compile(r"^(n|v|vt|vi|adj|adv|prep|conj|pron|art|num|aux)\.?"
                    r"(/(n|v|vt|vi|adj|adv|prep|conj|pron|art|num|aux)\.?)*$")
CJK = re.compile(r"[\u4e00-\u9fff]")


def valid(word, rec, problems):
    if not isinstance(rec, dict):
        problems.append(f"{word}: not an object")
        return False
    ok = True
    for f in ("cn", "phrase_cn"):
        if rec.get(f) and not CJK.search(rec[f]):
            problems.append(f"{word}: {f} has no Chinese")
            rec.pop(f)
    if rec.get("pos") and not POS_OK.match(rec["pos"].strip()):
        problems.append(f"{word}: bad pos {rec['pos']!r}")
        rec.pop("pos")
    if rec.get("example") and "  " not in rec["example"]:
        problems.append(f"{word}: example missing the two-space separator")
    if rec.get("ipa"):
        v = rec["ipa"].strip().strip("/[]")
        bad = {c for c in v if c not in IPA_OK}
        if bad or not v:
            problems.append(f"{word}: bad ipa {rec['ipa']!r} {bad}")
            rec.pop("ipa")
        else:
            rec["ipa"] = v
    if rec.get("spoken") is not None:
        try:
            s = int(rec["spoken"])
            rec["spoken"] = max(0, min(5, s))
        except (TypeError, ValueError):
            rec.pop("spoken")
    return ok


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else ""
    cache_path = os.path.join(DATA, "enrich_cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    problems, merged, files = [], 0, 0
    for name in sorted(os.listdir(BATCH)):
        if not name.endswith(".out.json") or not name.startswith(prefix):
            continue
        files += 1
        try:
            data = json.load(open(os.path.join(BATCH, name)))
        except Exception as exc:
            problems.append(f"{name}: unreadable ({exc})")
            continue
        if isinstance(data, list):
            data = {d.get("word"): d for d in data if isinstance(d, dict)}
        for word, rec in data.items():
            if not word:
                continue
            valid(word, rec, problems)
            slot = cache.setdefault(word.lower(), {})
            for f in FIELDS:
                if rec.get(f) not in (None, ""):
                    slot[f] = rec[f]
            merged += 1
    json.dump(cache, open(cache_path, "w"), ensure_ascii=False, indent=1)
    print(f"merged {merged} records from {files} files; cache size {len(cache)}")
    if problems:
        print(f"{len(problems)} problems (first 15):")
        for p in problems[:15]:
            print("  " + p)


if __name__ == "__main__":
    main()
