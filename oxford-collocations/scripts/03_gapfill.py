"""Pass 03: 补回 Vision 漏识别的整行，就地更新 data/ocr/*.json。

Vision 会静默丢行，而且丢的多半就是加粗的习语条目行（例如 p1 右栏
`absence makes the heart grow ˈfonder` 整行没有输出）。丢一行就丢一个词条，
所以必须补。

检测：同一栏里相邻两行的 y 间距超过该页正常行距的 1.75 倍，说明中间空了一行以上。
补救：把那条空带单独裁出来，用 `en-US` 优先重 OCR（漏掉的基本都是纯英文的条目行，
中文优先反而更容易漏），识别到就按原格式插回去，并打上 `fill: True`。

Usage: 03_gapfill.py [起页 [止页]]
"""
import io
import json
import os
import statistics
import sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "牛津搭配词典.pdf")
OCR = os.path.join(ROOT, "data", "ocr")
DPI = 220
GAP = 1.75


def gaps(lines):
    """返回 [(y0, y1)]：同一栏里疑似漏行的纵向区间。"""
    out = []
    for lo, hi in ((0.0, 0.5), (0.5, 1.0)):
        col = sorted((l for l in lines if lo <= l["x"] < hi), key=lambda l: l["y"])
        if len(col) < 6:
            continue
        step = statistics.median(b["y"] - a["y"] for a, b in zip(col, col[1:]))
        if step <= 0:
            continue
        for a, b in zip(col, col[1:]):
            if b["y"] - a["y"] > step * GAP:
                out.append((a["y"] + a["h"] * 0.9, b["y"] - step * 0.15, lo, hi))
    return out


def run_page(n):
    import fitz
    from PIL import Image
    from ocrmac import ocrmac

    path = os.path.join(OCR, f"p{n:03d}.json")
    page = json.load(open(path))
    holes = gaps(page["lines"])
    if not holes:
        return n, 0

    doc = fitz.open(PDF)
    pix = doc[n - 1].get_pixmap(dpi=DPI)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    doc.close()
    W, H = img.size

    added = []
    for y0, y1, lo, hi in holes:
        box = (int(lo * W), max(0, int(y0 * H) - 2),
               int(hi * W), min(H, int(y1 * H) + 2))
        if box[3] - box[1] < 8:
            continue
        crop = img.crop(box)
        try:
            found = ocrmac.OCR(crop, language_preference=["en-US", "zh-Hans"],
                               recognition_level="accurate").recognize()
        except Exception:
            continue
        # 窄条带里 Vision 常把一行拆成几块（'absence' / 'makes' / 'the' / ...），
        # 按纵向位置聚成一行、再按横向顺序拼回去
        frags = [(1 - by - bh, bx, bw, bh, text, conf)
                 for text, conf, (bx, by, bw, bh) in found
                 if conf >= 0.3 and text.strip()]
        frags.sort()
        for frag in frags:
            if added and abs(frag[0] - added[-1]["_ry"]) < max(frag[3], 0.02) * 0.8:
                row = added[-1]
                row["_parts"].append((frag[1], frag[4]))
                row["w"] = round(max(row["w"], (frag[1] + frag[2]) * (hi - lo)), 4)
                continue
            added.append({"_ry": frag[0], "_parts": [(frag[1], frag[4])],
                          "_lo": lo, "_hi": hi,
                          "c": round(frag[5], 3), "fill": True,
                          "x": round(lo + frag[1] * (hi - lo), 4),
                          "y": round(y0 + frag[0] * (y1 - y0), 4),
                          "w": round(frag[2] * (hi - lo), 4),
                          "h": round(frag[3] * (y1 - y0), 4)})

    for row in added:
        parts = sorted(row.pop("_parts"))
        lo, hi = row.pop("_lo"), row.pop("_hi")
        row["t"] = " ".join(t for _, t in parts)
        row["x"] = round(lo + parts[0][0] * (hi - lo), 4)   # 整行左边界 = 最左碎片
        row.pop("_ry")
    added = [r for r in added if len(r["t"].strip()) >= 3]

    if added:
        page["lines"] += added
        page["lines"].sort(key=lambda l: (l["y"], l["x"]))
        json.dump(page, open(path, "w"), ensure_ascii=False)
    return n, len(added)


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 630
    todo = [n for n in range(a, b + 1)
            if os.path.exists(os.path.join(OCR, f"p{n:03d}.json"))]
    total = 0
    with Pool(4) as pool:
        for i, (n, k) in enumerate(pool.imap_unordered(run_page, todo), 1):
            total += k
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  累计补回 {total} 行")
    print(f"补回 {total} 行")


if __name__ == "__main__":
    main()
