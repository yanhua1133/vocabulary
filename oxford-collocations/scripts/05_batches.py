"""Pass 05: 切出给子 agent 校对的批次 → work/batches/。

规则清洗到这儿就到顶了，剩下的三类毛病只能靠模型：
- 解释里的 OCR 错字（`放 斧⋯而转向⋯` 其实是「放弃…而转向…」）
- 小类切分错位（`be left ~ed` 被切成 `eft abandoned`）
- 例句缺失——原书本来只给三成搭配配了例句，要「填满」只能生成

词头按词频从高到低排，先校对常用的那批：6200 个词头全做要 150 多个 agent，
先拿高频词头验证效果和成本。

Usage: 05_batches.py [词头数] [每批小类数]   (默认 100 个词头、40 条一批)
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
WORK = os.path.join(ROOT, "work", "batches")


def key_of(word, full):
    """用「词头 + 第一条搭配」当 key，不用位置。

    位置型 id（`word|义项|组|小类`）有两个毛病：抽取结构一改就全错位，
    而且 `name` 名词和 `name` 动词是两个词头、位置下标却一样，会撞 key。
    """
    return word + "||" + re.sub(r"[^a-z]", "", (full[0] if full else "").lower())


def main():
    n_head = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    from wordfreq import zipf_frequency

    book = json.load(open(os.path.join(DATA, "expanded.json")))
    ranked = sorted(book, key=lambda h: -zipf_frequency(h["word"].lower(), "en"))
    picked = ranked[:n_head]

    items, seen = [], set()
    for h in picked:
        for s in h["senses"]:
            for g in s["groups"]:
                for sub in g.get("subs") or []:
                    if not sub.get("full"):
                        continue
                    k = key_of(h["word"], sub["full"])
                    if k in seen:
                        continue
                    seen.add(k)
                    ex = sub.get("ex") or [["", ""]]
                    items.append({
                        "id": key_of(h["word"], sub["full"]),
                        "w": h["word"], "c": sub["full"],
                        "cn": sub["cn"],
                        "ex": f"{ex[0][0]}  {ex[0][1]}".strip()})

    os.makedirs(WORK, exist_ok=True)
    for f in os.listdir(WORK):
        os.remove(os.path.join(WORK, f))
    n = 0
    for start in range(0, len(items), size):
        n += 1
        with open(os.path.join(WORK, f"b{n:03d}.json"), "w") as fh:
            json.dump(items[start:start + size], fh, ensure_ascii=False)
    print(f"{len(picked)} 个高频词头 → {len(items)} 条小类 → {n} 个批次")
    print(f"（全书 {len(book)} 个词头，"
          f"{sum(len(g.get('subs') or []) for h in book for s in h['senses'] for g in s['groups'])} 条小类）")


if __name__ == "__main__":
    main()
