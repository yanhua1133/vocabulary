"""Pass 3: extract every glyph run ("token") as a sequence of cluster ids.

Runs that fall inside a ［...］ phonetic bracket are tagged "ipa" - the bracket
characters come from a Chinese font with a real ToUnicode map, so they can be
located geometrically even though PyMuPDF splits them into separate lines.

Outputs data/tokens.json {"clusters": [...], "tokens": [[page, [cid...], kind, face], ...]}
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from glyphs import GlyphResolver, family

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def ipa_regions(raw):
    opens, closes = [], []
    for blk in raw["blocks"]:
        for line in blk.get("lines", []):
            for span in line["spans"]:
                for ch in span["chars"]:
                    b = ch["bbox"]
                    yc = (b[1] + b[3]) / 2
                    if ch["c"] in "［[":
                        opens.append((yc, b[2]))
                    elif ch["c"] in "］]":
                        closes.append((yc, b[0]))
    closes.sort()
    regions = []
    used = set()
    for yc, x1 in sorted(opens):
        best = None
        for j, (yc2, x0) in enumerate(closes):
            if j in used or abs(yc2 - yc) > 3 or x0 <= x1:
                continue
            if best is None or x0 < closes[best][1]:
                best = j
        if best is not None:
            used.add(best)
            regions.append((yc, x1, closes[best][1]))
    return regions


def in_ipa(regions, bbox):
    xc = (bbox[0] + bbox[2]) / 2
    yc = (bbox[1] + bbox[3]) / 2
    return any(abs(yc - ry) <= 3 and rx0 <= xc <= rx1 for ry, rx0, rx1 in regions)


def main():
    res = GlyphResolver(os.path.join(ROOT, "GRE3000.pdf"))
    order = json.load(open(os.path.join(DATA, "cluster_order.json")))
    cid = {h: i for i, h in enumerate(order)}

    tokens = []
    for pno in range(len(res.doc)):
        raw = res.doc[pno].get_text("rawdict")
        regions = ipa_regions(raw)
        for blk in raw["blocks"]:
            for line in blk.get("lines", []):
                cur, cur_face, cur_kind, prev_x1 = [], None, None, None
                for span in line["spans"]:
                    fam = family(span["font"])
                    for ch in span["chars"]:
                        c = ch["c"]
                        h = None if c == " " else res.hash(pno, span["font"], c)
                        if h is None:
                            if cur:
                                tokens.append([pno, cur, cur_kind, cur_face])
                            cur, cur_face, cur_kind, prev_x1 = [], None, None, None
                            continue
                        kind = "ipa" if in_ipa(regions, ch["bbox"]) else "text"
                        gap = prev_x1 is not None and ch["bbox"][0] - prev_x1 > 0.9
                        if cur and (gap or fam != cur_face or kind != cur_kind):
                            tokens.append([pno, cur, cur_kind, cur_face])
                            cur = []
                        cur.append(cid[h])
                        cur_face, cur_kind = fam, kind
                        prev_x1 = ch["bbox"][2]
                if cur:
                    tokens.append([pno, cur, cur_kind, cur_face])
        if pno % 60 == 0:
            print("  page", pno, "tokens", len(tokens), flush=True)

    json.dump({"clusters": order, "tokens": tokens},
              open(os.path.join(DATA, "tokens.json"), "w"))
    kinds = {}
    for t in tokens:
        kinds[t[2]] = kinds.get(t[2], 0) + 1
    print("tokens:", len(tokens), kinds)


if __name__ == "__main__":
    main()
