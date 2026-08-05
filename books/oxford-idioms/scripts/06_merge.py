"""Pass 06: 校验并并入子 agent 写出的 work/batches/*.out.json → data/cache.json。

只接受形状对、字段齐的条目；缺一样就整条丢掉并计数，别让半成品混进成品。

Usage: 06_merge.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
WORK = os.path.join(ROOT, "work", "batches")
CACHE = os.path.join(DATA, "cache.json")
CJK = re.compile(r"[\u4e00-\u9fff]")


def ok(rec):
    if not isinstance(rec, dict):
        return False
    idiom, cn, ex = rec.get("i", ""), rec.get("cn", ""), rec.get("e", "")
    if not (idiom and cn and ex):
        return False
    if not CJK.search(cn) or CJK.search(idiom):
        return False
    en, _, cn_ex = ex.partition("  ")          # 例句格式：英文 + 两个空格 + 中文
    return bool(re.search(r"[A-Za-z]", en)) and bool(CJK.search(cn_ex))


def main():
    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE))
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
        for key, rec in data.items():
            if ok(rec):
                cache[str(key)] = rec
                good += 1
            else:
                bad += 1
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
    print(f"{files} 个输出文件：合格 {good}，丢弃 {bad}；缓存共 {len(cache)} 条")


if __name__ == "__main__":
    main()
