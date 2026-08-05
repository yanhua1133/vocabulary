"""Pass 1: inventory every glyph outline in the book, with outline metrics.

Outputs data/clusters.json:
  hash -> {count, faces, ink (font units), width, rep {page,bbox,size,ascender,face}}
and data/cluster_order.json (hashes sorted by frequency).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from glyphs import GlyphResolver, family

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def main():
    os.makedirs(DATA, exist_ok=True)
    res = GlyphResolver(os.path.join(ROOT, "GRE3000.pdf"))
    clusters = {}
    for pno in range(len(res.doc)):
        raw = res.doc[pno].get_text("rawdict")
        for blk in raw["blocks"]:
            for line in blk.get("lines", []):
                for span in line["spans"]:
                    fam = family(span["font"])
                    for ch in span["chars"]:
                        c = ch["c"]
                        if c == " ":
                            continue
                        h = res.hash(pno, span["font"], c)
                        if h is None:
                            continue
                        rec = clusters.get(h)
                        if rec is None:
                            ink, width, nseg, isbox = res.metrics(pno, span["font"], c)
                            rec = clusters[h] = {
                                "count": 0, "faces": {}, "rep": None,
                                "ink": [round(v) for v in ink] if ink else None,
                                "width": width, "nseg": nseg, "isbox": isbox,
                            }
                        rec["count"] += 1
                        rec["faces"][fam] = rec["faces"].get(fam, 0) + 1
                        if rec["rep"] is None or span["size"] > rec["rep"]["size"] + 0.6:
                            rec["rep"] = {
                                "page": pno,
                                "bbox": [round(v, 2) for v in ch["bbox"]],
                                "size": round(span["size"], 3),
                                "ascender": round(span["ascender"], 4),
                                "face": fam,
                            }
        if pno % 60 == 0:
            print(f"  page {pno} clusters={len(clusters)}", flush=True)

    json.dump(clusters, open(os.path.join(DATA, "clusters.json"), "w"), indent=1)
    order = sorted(clusters, key=lambda h: -clusters[h]["count"])
    json.dump(order, open(os.path.join(DATA, "cluster_order.json"), "w"), indent=1)
    print("clusters", len(clusters))
    noink = [h for h in clusters if not clusters[h]["ink"]]
    print("clusters without outline bounds (blank glyphs):", len(noink))


if __name__ == "__main__":
    main()
