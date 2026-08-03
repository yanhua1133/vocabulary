"""Shared helpers for reading the book's obfuscated text layer.

The PDF embeds subsetted CFF fonts whose glyphs are named G21, G22, ... in
order of first use, with no ToUnicode map.  The outlines themselves are
identical across subsets, so hashing a glyph's charstring gives a stable
identity for the underlying character shape.
"""
import hashlib
import io
import re

import fitz
from fontTools.cffLib import CFFFontSet
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen

PDF = "GRE3000.pdf"
SUBSET_TAG = re.compile(r"^\w{6}\+")


def strip_tag(name):
    return SUBSET_TAG.sub("", name)


def family(fontname):
    """DLF-3-12-283781260 -> DLF-3-12"""
    return strip_tag(fontname).rsplit("-", 1)[0]


class GlyphResolver:
    def __init__(self, path=PDF):
        self.doc = fitz.open(path)
        self._fonts = {}                # xref -> (CharStrings, glyphSet) | None
        self._page_fonts = {}           # pno -> {plain name: (xref, ext)}
        self._bounds = {}               # (xref, gname) -> bbox | None

    def page_fonts(self, pno):
        if pno not in self._page_fonts:
            self._page_fonts[pno] = {
                strip_tag(name): (xref, ext)
                for xref, ext, _typ, name, *_ in self.doc.get_page_fonts(pno)
            }
        return self._page_fonts[pno]

    def _font(self, xref, ext):
        if xref not in self._fonts:
            val = None
            if ext == "cff":
                try:
                    buf = self.doc.extract_font(xref)[3]
                    cff = CFFFontSet()
                    cff.decompile(io.BytesIO(buf), None)
                    td = cff[cff.fontNames[0]]
                    val = (td.CharStrings, td.CharStrings)
                except Exception:
                    val = None
            self._fonts[xref] = val
        return self._fonts[xref]

    def _lookup(self, pno, fontname, char):
        entry = self.page_fonts(pno).get(strip_tag(fontname))
        if entry is None:
            return None, None
        font = self._font(*entry)
        if font is None:
            return None, None
        gname = "G%02X" % ord(char)
        cs = font[0]
        if gname not in cs:
            return None, None
        return entry[0], (cs, gname)

    def hash(self, pno, fontname, char):
        """Stable identity for a character occurrence, or None."""
        _xref, got = self._lookup(pno, fontname, char)
        if got is None:
            return None
        cs, gname = got
        return hashlib.md5(cs[gname].bytecode or b"").hexdigest()[:12]

    def metrics(self, pno, fontname, char):
        """(ink_bbox_in_font_units, advance_width, path_segments) or (None,)*3."""
        xref, got = self._lookup(pno, fontname, char)
        if got is None:
            return None, None, None
        cs, gname = got
        key = (xref, gname)
        if key not in self._bounds:
            g = cs[gname]
            bbox = width = nseg = None
            isbox = False
            try:
                pen = BoundsPen(cs)
                g.draw(pen)
                bbox = pen.bounds
                rec = RecordingPen()
                g.draw(rec)
                nseg = len(rec.value)
                width = g.width
                pts = [p for op, args in rec.value for p in args
                       if op in ("moveTo", "lineTo")]
                isbox = (len(pts) == 4
                         and len({round(p[0]) for p in pts}) == 2
                         and len({round(p[1]) for p in pts}) == 2)
            except Exception:
                pass
            self._bounds[key] = (bbox, width, nseg, isbox)
        return self._bounds[key]


def ink_rect(char_bbox, span, ink_bbox):
    """Map a glyph's font-unit ink box onto the page."""
    size = span["size"]
    origin_y = char_bbox[1] + span["ascender"] * size
    x0 = char_bbox[0] + ink_bbox[0] * size / 1000.0
    x1 = char_bbox[0] + ink_bbox[2] * size / 1000.0
    y0 = origin_y - ink_bbox[3] * size / 1000.0
    y1 = origin_y - ink_bbox[1] * size / 1000.0
    return fitz.Rect(x0, y0, x1, y1)
