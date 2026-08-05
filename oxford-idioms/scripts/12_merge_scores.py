"""Pass 12: 校验并并入打分结果 work/scores/*.out.json → data/scores.json。

只收 0-5 的整数，别的一律丢掉并计数。

Usage: 12_merge_scores.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
WORK = os.path.join(ROOT, "work", "scores")
OUT = os.path.join(DATA, "scores.json")


def ok(v):
    return isinstance(v, int) and 0 <= v <= 5


def main():
    scores = json.load(open(OUT)) if os.path.exists(OUT) else {}
    good = bad = files = 0
    for f in sorted(os.listdir(WORK)):
        if not f.endswith(".out.json"):
            continue
        files += 1
        try:
            data = json.load(open(os.path.join(WORK, f)))
        except Exception as e:
            print(f"  {f} 解析失败：{e}")
            continue
        for k, rec in data.items():
            if isinstance(rec, dict) and ok(rec.get("u")) and ok(rec.get("s")):
                scores[k] = {"u": rec["u"], "s": rec["s"]}
                good += 1
            else:
                bad += 1
    json.dump(scores, open(OUT, "w"), ensure_ascii=False)
    print(f"{files} 个输出文件：合格 {good}，丢弃 {bad}；共 {len(scores)} 条")


if __name__ == "__main__":
    main()
