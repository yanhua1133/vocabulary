"""Decode a page into styled spans using the solved glyph labels."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from glyphs import GlyphResolver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


class Decoder:
    def __init__(self):
        self.res = GlyphResolver(os.path.join(ROOT, "GRE3000.pdf"))
        self.labels = json.load(open(os.path.join(DATA, "labels_solved.json")))
        for name in ("labels_manual.json", "labels_fix.json"):
            p = os.path.join(DATA, name)
            if os.path.exists(p):
                self.labels.update(json.load(open(p)))
        self.clusters = json.load(open(os.path.join(DATA, "clusters.json")))

    def char(self, pno, fontname, c):
        h = self.res.hash(pno, fontname, c)
        if h is None:
            return c            # Chinese / already-unicode glyph
        lab = self.labels.get(h, "")
        return lab if lab else "\ufffd"

    def spans(self, pno):
        raw = self.res.doc[pno].get_text("rawdict")
        out = []
        for blk in raw["blocks"]:
            for line in blk.get("lines", []):
                sp = []
                for span in line["spans"]:
                    txt = "".join(
                        " " if ch["c"] == " " else self.char(pno, span["font"], ch["c"])
                        for ch in span["chars"]
                    )
                    sp.append({
                        "text": txt,
                        "face": span["font"].rsplit("-", 1)[0],
                        "size": round(span["size"], 1),
                        "color": span["color"],
                        "bbox": [round(v, 1) for v in span["bbox"]],
                    })
                out.append(sp)
        return out

    def text(self, pno):
        return "\n".join("".join(s["text"] for s in line) for line in self.spans(pno))

    def ipa_items(self, pno):
        """[{y, x, text}] for every ［...］ phonetic bracket on the page."""
        return self._ipa(pno, with_pos=True)

    def ipa_strings(self, pno):
        """Decoded contents of every ［...］ phonetic bracket on the page.

        Brackets and their contents land in different PyMuPDF line objects, so
        the regions are paired geometrically and filled by x order.
        """
        return self._ipa(pno, with_pos=False)

    def _ipa(self, pno, with_pos):
        raw = self.res.doc[pno].get_text("rawdict")
        opens, closes, chars = [], [], []
        for blk in raw["blocks"]:
            for line in blk.get("lines", []):
                for span in line["spans"]:
                    for ch in span["chars"]:
                        b = ch["bbox"]
                        yc = (b[1] + b[3]) / 2
                        if ch["c"] in "［[":
                            opens.append((yc, b[0]))
                        elif ch["c"] in "］]":
                            closes.append((yc, b[0]))
                        else:
                            chars.append((yc, b[0], self.char(pno, span["font"], ch["c"])))
        out = []
        used = set()
        for yc, x1 in sorted(opens):
            best = None
            for j, (yc2, x0) in enumerate(closes):
                if j in used or abs(yc2 - yc) > 3 or x0 <= x1:
                    continue
                if best is None or x0 < closes[best][1]:
                    best = j
            if best is None:
                continue
            used.add(best)
            x2 = closes[best][1]
            inside = sorted((x, c) for cy, x, c in chars
                            if abs(cy - yc) <= 3 and x1 <= x <= x2)
            s = "".join(c for _x, c in inside).strip()
            if s:
                out.append({"y": yc, "x": x1, "text": s} if with_pos else s)
        return out


if __name__ == "__main__":
    d = Decoder()
    for a in sys.argv[1:]:
        print(f"===== page {a} =====")
        print(d.text(int(a)))
