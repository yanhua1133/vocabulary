"""Pass 06: 并入子 agent 校对的结果 → data/cache.json。

只收形状对、字段齐的：`cn` 必须是纯中文，`ex` 必须是「英文 + 两个空格 + 中文」
且英文部分够长。不合格的整条丢掉并计数，别让半成品混进成品。

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
    cn, ex = rec.get("cn", ""), rec.get("ex", "")
    if not cn or not CJK.search(cn) or re.search(r"[a-zA-Z]{4,}", cn):
        return False
    if "~" in cn or "|" in cn:
        return False
    en, _, zh = ex.partition("  ")
    return (len(en.split()) >= 5 and en.rstrip().endswith((".", "!", "?"))
            and bool(CJK.search(zh)))


def main():
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
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
            # 只收新式 key（`词头||搭配`）。上一轮用的是位置型 id（`词头|义项|组|小类`），
            # 那批 agent 是在批次目录清空之后才写完的，混进来会污染
            if "||" not in key:
                bad += 1
                continue
            if ok(rec):
                cache[key] = {"cn": rec["cn"].strip(), "ex": rec["ex"].strip()}
                good += 1
            else:
                bad += 1
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
    print(f"{files} 个输出文件：合格 {good}，丢弃 {bad}；缓存共 {len(cache)} 条")


if __name__ == "__main__":
    main()
