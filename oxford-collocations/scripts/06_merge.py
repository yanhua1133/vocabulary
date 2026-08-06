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


def merge_fix(cache):
    """并入 work/fix/ 里修好的搭配。这批不光改 cn/ex，还改搭配文本本身
    （`time him` → `the mists of time`），推不出来的标了 `__DROP__`，整条删掉。"""
    fixed = dropped = 0
    for d in (os.path.join(ROOT, "work", "fix"),
              os.path.join(ROOT, "work", "fix2"),
              os.path.join(ROOT, "work", "fix3")):
        if not os.path.isdir(d):
            continue
        fixed, dropped = _merge_dir(d, cache, fixed, dropped)
    return fixed, dropped


def reconcile(cache):
    """对账：把渲染查不到的孤儿 key 搬回正确的 key 上。

    自查脚本导出 id 时用的是修正后的搭配、渲染查缓存用的是抽取阶段的原始搭配，
    改过一轮之后两边就对不上了。孤儿 key 存着最新的修正结果，却永远读不到，
    成品里显示的还是上一轮的旧内容。
    """
    book = json.load(open(os.path.join(DATA, "expanded.json")))
    valid = set()
    for h in book:
        for s in h["senses"]:
            for g in s["groups"]:
                for sub in g.get("subs") or []:
                    full = sub.get("full") or []
                    if full:
                        valid.add(h["word"] + "||"
                                  + re.sub(r"[^a-z]", "", full[0].lower()))
    moved = 0
    for k in list(cache):
        if k in valid or k.startswith("!drop!"):
            continue
        rec = cache[k]
        word, _, tail = k.partition("||")
        for vk in valid:
            if not vk.startswith(word + "||"):
                continue
            c = (cache.get(vk) or {}).get("c") or []
            if c and re.sub(r"[^a-z]", "", c[0].lower()) == tail:
                cache[vk] = rec       # 孤儿里存的是更新的那份
                del cache[k]
                moved += 1
                break
    return moved


def _resolve(key, cache):
    """key 漂移的补救：自查脚本导出 id 时用的是**修正后**的搭配，
    而渲染查缓存用的是抽取阶段的原始搭配，两边对不上，改好的东西就落不到成品里。
    对不上时，拿 key 后半去比对已有条目修好的搭配，找回原来的 key。"""
    if key in cache:
        return key
    word, _, tail = key.partition("||")
    for k, v in cache.items():
        if not k.startswith(word + "||"):
            continue
        c = v.get("c") or []
        if c and re.sub(r"[^a-z]", "", c[0].lower()) == tail:
            return k
    return key


def _merge_dir(d, cache, fixed, dropped):
    for f in sorted(os.listdir(d)):
        if not f.endswith(".out.json"):
            continue
        try:
            data = json.load(open(os.path.join(d, f)))
        except Exception as e:
            print(f"  {f} 解析失败：{e}")
            continue
        for key, rec in data.items():
            key = _resolve(key, cache)
            c = rec.get("c") or []
            if "__DROP__" in c:
                cache.pop(key, None)
                cache["!drop!" + key] = {"cn": "", "ex": "", "drop": True}
                dropped += 1
            elif c and ok(rec):
                cache[key] = {"cn": rec["cn"].strip(), "ex": rec["ex"].strip(),
                              "c": c}
                fixed += 1
    return fixed, dropped


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
    fixed, dropped = merge_fix(cache)
    moved = reconcile(cache)
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
    print(f"{files} 个输出文件：合格 {good}，丢弃 {bad}；缓存共 {len(cache)} 条")
    if fixed or dropped:
        print(f"  修好搭配 {fixed} 条，推不出来丢掉 {dropped} 条")
    if moved:
        print(f"  把 {moved} 条搬回渲染能查到的 key 上")


if __name__ == "__main__":
    main()
