"""Pass 4: recover cluster -> letter by maximising English-dictionary hits.

Only clusters that can plausibly be letters take part: IPA-only glyphs, small
punctuation marks, digits and solid ornaments are frozen out and left for
manual labelling (pass 5).  Identity is solved case-insensitively, then case is
decided by voting on the case context of each occurrence.

Outputs data/labels_solved.json {hash: letter or ""} and data/frozen.json.
"""
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CANDIDATES = list("abcdefghijklmnopqrstuvwxyz") + [""]
# lowercase forms topped at x-height: case is decidable from ink height alone
NO_ASCENDER = set("acegmnopqrsuvwxyz")
# lowercase forms as tall as capitals: case needs context voting
AMBIGUOUS = set("bdfhijklt")


def load_dict():
    words = set()
    for path in ("/usr/share/dict/web2", "/usr/share/dict/web2a"):
        if os.path.exists(path):
            with open(path, encoding="latin-1") as fh:
                for w in fh:
                    w = w.strip().lower()
                    if w.isalpha():
                        words.add(w)
    extra = set()
    for w in words:
        if len(w) > 2:
            extra.add(w + "s")
            if w.endswith("e"):
                extra.add(w + "d")
                extra.add(w[:-1] + "ing")
            else:
                extra.add(w + "ed")
                extra.add(w + "ing")
    return words | extra


def freeze_set(order, clusters, auto, ipa_hits, text_hits):
    frozen = {}
    for i, h in enumerate(order):
        rec = clusters[h]
        ink = rec["ink"]
        why = None
        if ipa_hits[i] and not text_hits[i]:
            why = "ipa"
        elif not ink:
            why = "blank"
        else:
            wid, hgt = ink[2] - ink[0], ink[3] - ink[1]
            if hgt < 330:
                why = "punct"
            elif rec.get("isbox") and wid >= 300 and hgt >= 300:
                why = "ornament"     # solid marker box, not a letter
        if why:
            frozen[i] = why
    return frozen


def main():
    tok = json.load(open(os.path.join(DATA, "tokens.json")))
    order = tok["clusters"]
    clusters = json.load(open(os.path.join(DATA, "clusters.json")))
    auto = {int(k): v for k, v in json.load(open(os.path.join(DATA, "labels_auto.json"))).items()}
    words = load_dict()
    n = len(order)

    ipa_hits, text_hits = [0] * n, [0] * n
    for _p, cids, kind, _f in tok["tokens"]:
        for c in cids:
            (ipa_hits if kind == "ipa" else text_hits)[c] += 1

    frozen = freeze_set(order, clusters, auto, ipa_hits, text_hits)
    print("frozen:", {v: sum(1 for x in frozen.values() if x == v) for v in set(frozen.values())})
    json.dump({order[i]: why for i, why in frozen.items()},
              open(os.path.join(DATA, "frozen.json"), "w"), indent=1)

    toks = [t[1] for t in tok["tokens"] if t[2] == "text" and 1 <= len(t[1]) <= 30]
    print(f"dictionary {len(words)}, clusters {n}, frozen {len(frozen)}, tokens {len(toks)}")

    labels = [""] * n
    for i in range(n):
        g = "".join(c for c in auto.get(i, "") if c.isalpha())
        labels[i] = g[0].lower() if g and i not in frozen else ""

    index = defaultdict(list)
    for ti, t in enumerate(toks):
        for c in set(t):
            index[c].append(ti)

    def score(tids):
        s = 0
        for ti in tids:
            for part in "".join(labels[c] or " " for c in toks[ti]).split():
                if len(part) >= 3 and part in words:
                    s += len(part)
        return s

    total = score(range(len(toks)))
    print("initial score", total)
    by_count = sorted(range(n), key=lambda i: -clusters[order[i]]["count"])
    for it in range(8):
        changed = 0
        for c in by_count:
            if c in frozen or c not in index:
                continue
            base = labels[c]
            cur = best_s = score(index[c])
            best = base
            for cand in CANDIDATES:
                if cand == base:
                    continue
                labels[c] = cand
                s = score(index[c])
                if s > best_s:
                    best, best_s = cand, s
            labels[c] = best
            if best != base:
                changed += 1
                total += best_s - cur
        print(f"pass {it}: changed {changed} score {total}", flush=True)
        if not changed:
            break

    # ---- case: height settles x-height letters, context voting settles the rest
    tallness = {}
    for i in range(n):
        ink = clusters[order[i]]["ink"]
        tallness[i] = (ink[3] if ink else 0) >= 600
    case = {}
    for i in range(n):
        if labels[i] in NO_ASCENDER:
            case[i] = "U" if tallness[i] else "L"
    votes = defaultdict(lambda: [0, 0])   # cluster -> [upper, lower]
    for t in toks:
        known = [case[c] for c in t if c in case]
        ctx = None
        if known and all(k == "U" for k in known):
            ctx = "U"
        elif known and all(k == "L" for k in known):
            ctx = "L"
        for j, c in enumerate(t):
            if labels[c] not in AMBIGUOUS:
                continue
            if ctx == "U":
                votes[c][0] += 1
            elif ctx == "L":
                votes[c][1 if j else 0] += 1
    for i in range(n):
        if labels[i] in AMBIGUOUS:
            up, lo = votes[i]
            if up == lo == 0:
                g = "".join(c for c in auto.get(i, "") if c.isalpha())
                case[i] = "U" if (g[:1].isupper() and tallness[i]) else "L"
            else:
                case[i] = "U" if up > lo else "L"
    for i in range(n):
        if labels[i] and case.get(i) == "U":
            labels[i] = labels[i].upper()
    print("uppercase clusters", sum(1 for i in range(n) if labels[i].isupper()))

    hits = sum(
        1 for t in toks
        for s in ["".join(labels[c].lower() or " " for c in t)]
        if s.strip() and all(len(p) < 3 or p in words for p in s.split())
    )
    print(f"tokens fully decodable: {hits}/{len(toks)} = {hits/len(toks):.3%}")
    json.dump({order[i]: labels[i] for i in range(n)},
              open(os.path.join(DATA, "labels_solved.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
