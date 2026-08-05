"""Pass 2: crop every cluster tightly using its outline bounds, ask tesseract
for a first guess, and render contact sheets annotated with that guess.

Outputs work/glyphs/NNNN.png and data/labels_auto.json.
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from glyphs import GlyphResolver, ink_rect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
GDIR = os.path.join(ROOT, "work", "glyphs")
SHEETS = os.path.join(ROOT, "work", "sheets")
WHITELIST = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
COLS, ROWS = 10, 12
CELL_W, CELL_H = 100, 104


def crop_all(res, order, clusters):
    os.makedirs(GDIR, exist_ok=True)
    for idx, h in enumerate(order):
        out = os.path.join(GDIR, f"{idx:04d}.png")
        if os.path.exists(out):
            continue
        rec = clusters[h]
        rep = rec["rep"]
        if not rec["ink"]:
            Image.new("L", (40, 110), 255).save(out)
            continue
        rect = ink_rect(rep["bbox"], {"size": rep["size"], "ascender": rep["ascender"]},
                        rec["ink"])
        rect = rect + (-0.15, -0.15, 0.15, 0.15)
        pix = res.doc[rep["page"]].get_pixmap(clip=rect, dpi=900, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
        scale = 110 / max(img.height, 1)
        img = img.resize((max(1, int(img.width * scale)), 110), Image.LANCZOS)
        canvas = Image.new("L", (img.width + 90, img.height + 90), 255)
        canvas.paste(img, (45, 45))
        canvas.save(out)


def tess(n):
    guesses = {}
    for idx in range(n):
        p = os.path.join(GDIR, f"{idx:04d}.png")
        r = subprocess.run(
            ["tesseract", p, "-", "--psm", "10", "-c",
             f"tessedit_char_whitelist={WHITELIST}"],
            capture_output=True, text=True,
        )
        guesses[idx] = r.stdout.strip().replace("\n", "")
        if idx % 100 == 0:
            print("  tess", idx, repr(guesses[idx]), flush=True)
    return guesses


def render(order, clusters, guesses):
    os.makedirs(SHEETS, exist_ok=True)
    try:
        f_big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
        f_sm = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    except OSError:
        f_big = f_sm = ImageFont.load_default()
    per = COLS * ROWS
    for start in range(0, len(order), per):
        chunk = order[start : start + per]
        sheet = Image.new("RGB", (COLS * CELL_W, ROWS * CELL_H), "white")
        d = ImageDraw.Draw(sheet)
        for i, h in enumerate(chunk):
            idx = start + i
            col, row = i % COLS, i // COLS
            x0, y0 = col * CELL_W, row * CELL_H
            d.rectangle([x0, y0, x0 + CELL_W - 1, y0 + CELL_H - 1], outline="#bbbbbb")
            d.text((x0 + 3, y0 + 1), str(idx), fill="#0066cc", font=f_sm)
            d.text((x0 + CELL_W - 26, y0 + 1), guesses.get(idx) or "?",
                   fill="#cc0000", font=f_big)
            ink = clusters[h]["ink"]
            if ink:
                d.text((x0 + 3, y0 + CELL_H - 14),
                       f"y{ink[1]}..{ink[3]}", fill="#888888", font=f_sm)
            img = Image.open(os.path.join(GDIR, f"{idx:04d}.png"))
            maxw, maxh = CELL_W - 12, CELL_H - 42
            sc = min(maxw / img.width, maxh / img.height)
            img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))),
                             Image.LANCZOS)
            sheet.paste(img.convert("RGB"), (x0 + (CELL_W - img.width) // 2, y0 + 24))
        p = os.path.join(SHEETS, f"s{start:04d}.png")
        sheet.save(p)
        print("wrote", p)


def main():
    res = GlyphResolver(os.path.join(ROOT, "GRE3000.pdf"))
    clusters = json.load(open(os.path.join(DATA, "clusters.json")))
    order = json.load(open(os.path.join(DATA, "cluster_order.json")))
    crop_all(res, order, clusters)
    cache = os.path.join(DATA, "labels_auto.json")
    if os.path.exists(cache):
        guesses = {int(k): v for k, v in json.load(open(cache)).items()}
    else:
        guesses = tess(len(order))
        json.dump(guesses, open(cache, "w"), indent=1)
    render(order, clusters, guesses)


if __name__ == "__main__":
    main()
