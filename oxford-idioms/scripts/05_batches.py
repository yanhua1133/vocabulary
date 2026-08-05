"""Pass 05: 把 data/idioms.json 切成给子 agent 的批次文件 → work/batches/。

每条给模型的输入尽量短：序号 + 关键词 + 条目原文 + 原书中文释义（OCR 抽的，可能空或有错）。
模型要回三样：修正后的条目写法、干净的中文释义、一句例句（英文 + 中文）。

原书例句不直接用——OCR 出来常带噪声（`挑件蓝色的东西吧,求个 吉利。 2`），
跟 GRE3000 一样，例句一律重写。

Usage: 05_batches.py [每批条数]   (默认 50)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
WORK = os.path.join(ROOT, "work", "batches")


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    book = json.load(open(os.path.join(DATA, "idioms.json")))
    items = []
    for h in book:
        for it in h["idioms"]:
            items.append({"id": len(items), "w": h["word"],
                          "i": it["idiom"], "cn": it["cn"]})
    os.makedirs(WORK, exist_ok=True)
    for f in os.listdir(WORK):
        os.remove(os.path.join(WORK, f))
    n = 0
    for start in range(0, len(items), size):
        n += 1
        with open(os.path.join(WORK, f"b{n:03d}.json"), "w") as fh:
            json.dump(items[start:start + size], fh, ensure_ascii=False)
    print(f"{len(items)} 条 → {n} 个批次，每批 {size} 条，在 {WORK}/")


if __name__ == "__main__":
    main()
