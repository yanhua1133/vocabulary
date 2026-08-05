"""Pass 01: 把《牛津习语词典》630 页扫描图 OCR 成 data/ocr/pNNN.json。

原书是 FreePic2Pdf 生成的纯扫描件，每页一张 JPEG，没有任何文字层，只能 OCR。
用 macOS Vision（本地、离线、中英混排质量远好于 tesseract；机器上的 tesseract
也只装了 eng 语言包）。

两个踩过的坑，别改：
- `language_preference` 第一位必须是 `zh-Hans`，写成 `en-US` 在前时中文整段丢失，
  只吐出 `thiE#` 这样的乱码。
- 220dpi 就够，300dpi 结果一样但更慢。

Usage: 01_ocr.py [起页 [止页]]   (默认全书；已生成的页会跳过)
"""
import io
import json
import os
import sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "牛津习语词典.pdf")
OCR = os.path.join(ROOT, "data", "ocr")
DPI = 220
LANGS = ["zh-Hans", "en-US"]


def page_path(n):
    return os.path.join(OCR, f"p{n:03d}.json")


def run_page(n):
    """n 是 1-based 页码。"""
    import fitz
    from PIL import Image
    from ocrmac import ocrmac

    doc = fitz.open(PDF)
    pix = doc[n - 1].get_pixmap(dpi=DPI)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    doc.close()

    lines = []
    for text, conf, box in ocrmac.OCR(
            img, language_preference=LANGS, recognition_level="accurate").recognize():
        x, y, w, h = box                      # Vision 的原点在左下角
        lines.append({"t": text, "c": round(conf, 3),
                      "x": round(x, 4), "y": round(1 - y - h, 4),
                      "w": round(w, 4), "h": round(h, 4)})
    lines.sort(key=lambda l: (l["y"], l["x"]))
    with open(page_path(n), "w") as fh:
        json.dump({"page": n, "w": pix.width, "h": pix.height, "lines": lines},
                  fh, ensure_ascii=False)
    return n, len(lines)


def main():
    import fitz

    os.makedirs(OCR, exist_ok=True)
    total = fitz.open(PDF).page_count
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else total
    todo = [n for n in range(a, b + 1) if not os.path.exists(page_path(n))]
    print(f"全书 {total} 页，本次要做 {len(todo)} 页")
    if not todo:
        return
    with Pool(4) as pool:
        for i, (n, k) in enumerate(pool.imap_unordered(run_page, todo), 1):
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  最近一页 p{n} {k} 行")
    print(f"完成，结果在 {OCR}/")


if __name__ == "__main__":
    main()
