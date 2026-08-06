"""Pass 08: 成品自查。把已经踩过的坑逐条查一遍，跑到数字收敛为止。

查的是**渲染成品的每一个格子**，不是中间数据。每一条都对应一个真实犯过的错：

- 搭配里夹数字      `g0od time`（OCR 把 o 认成 0，纠错时被 isalpha 挡掉了）
- 搭配其实是例句    `s this an appropriate time to discuss salary?`（还掉了首字母）
- 搭配首字母缺失    `ocal`→local、`ife`→life
- 解释里混英文      没摘干净的例句
- 例句不完整        缺主语、没有句末标点
- 例句加粗不全      `an appropriate time` 只标了 time

Usage: 08_audit.py
"""
import importlib.util
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CJK = re.compile(r"[\u4e00-\u9fff]")

spec = importlib.util.spec_from_file_location("p07", os.path.join(HERE, "07_render.py"))
p07 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p07)

# 搭配里允许出现的非字母：占位符、括号标签、斜杠变体
PLACE = {"sb", "sth", "sb's", "sth's", "one's", "etc", "esp", "brE", "amE"}
# 英式拼写在 wordfreq 里词频普遍偏低，别当成 OCR 错字
BRITISH = {"belabour", "labour", "favour", "honour", "colour", "flavour",
           "behaviour", "neighbour", "endeavour", "rumour", "humour",
           "practise", "organise", "recognise", "realise", "analyse"}


def rows_of():
    """跟渲染走同一条路，查的就是印出来的东西。"""
    book = json.load(open(os.path.join(DATA, "expanded.json")))
    cpath = os.path.join(DATA, "cache.json")
    cache = json.load(open(cpath)) if os.path.exists(cpath) else {}
    out = []
    for h in book:
        for s in h["senses"]:
            for g in s["groups"]:
                for sub in g.get("subs") or []:
                    full = sub.get("full") or []
                    if not full:
                        continue
                    key = h["word"] + "||" + re.sub(r"[^a-z]", "", full[0].lower())
                    if "!drop!" + key in cache:
                        continue
                    got = cache.get(key)
                    if got:
                        full = got.get("c") or full
                    full = [p07._p04.fix_phrase(x) for x in full]   # 跟渲染同一口径
                    if got:
                        en, _, zh = got["ex"].partition("  ")
                        out.append((h["word"], full, got["cn"], en, zh, True))
                    else:
                        ex = (sub.get("ex") or [["", ""]])[0]
                        out.append((h["word"], full, sub["cn"], ex[0], ex[1], False))

    return out


def check(rows):
    from wordfreq import zipf_frequency as z

    bad = {k: [] for k in (
        "搭配夹数字", "搭配其实是句子", "搭配有坏词", "搭配缺首字母",
        "解释混英文", "解释为空", "例句不完整", "例句加粗不全")}
    for word, full, cn, en, zh, *_ in rows:
        for f in full:
            # `a 16-digit number`、`an under-16 team` 里的数字是正经的
            if re.search(r"\d", f) and not re.search(r"[\d]+-\w|\w-[\d]+", f):
                bad["搭配夹数字"].append(f)
            # `what use is sth?`、`Way to go!` 是词典收的固定表达，不算句子；
            # 真正的毛病是整句正文被抽成了搭配，那种更长、而且有主谓宾
            # 带问号叹号的短表达是词典收的（`what use is sth?`、`Way to go!`），
            # 长的就是整句正文被抽进来了（`s this an appropriate time to discuss salary?`）
            if (re.search(r"[?!]", f) and len(f.split()) > 5) \
                    or len(f.split()) > 9 or re.search(
                    r"\b(this|that|there|it|he|she|they)\s+(is|was|are|were|has|had)\b",
                    f, re.I):
                bad["搭配其实是句子"].append(f)
            # 首字母被吃掉，剩个孤零零的字母打头：`n accepting the award`、
            # `s this an appropriate time`、`t stayed hot`。
            # a 和 I 是正经开头（`a matter of time`），排除掉
            if re.match(r"^[b-hj-z]\s", f, re.I) or re.search(r"\s[b-hj-z]\s", f):
                bad["搭配缺首字母"].append(f)
            for w in re.findall(r"[A-Za-z][a-z']{2,}", f):
                # 连字符复合词、加了前缀的词 wordfreq 常查不到，
                # 但它们是正经英语（semidetached、nanoplankton），别误报
                # 连字符复合词、带前缀后缀的派生词 wordfreq 常查不到，
                # 但都是正经英语（semidetached、pityingly、enquiringly），别误报
                if len(w) > 11 or re.match(
                        r"(semi|nano|micro|multi|inter|over|under|non|anti|pre|post)", w) \
                        or re.search(r"(ingly|edly|ously|ily|ness|ment|ship)$", w):
                    continue
                if w.lower() in BRITISH:      # 英式拼写 wordfreq 收得少
                    continue
                if w.lower() not in PLACE and z(w.lower(), "en") < 1.5:
                    bad["搭配有坏词"].append(f"{f}  ←{w}")
                    break
        if not cn or not CJK.search(cn):
            bad["解释为空"].append(f"{word}: {full[:1]}")
        elif re.search(r"[a-zA-Z]{4,}", cn):
            bad["解释混英文"].append(cn[:40])
        if en:
            if not en.rstrip().endswith((".", "!", "?")) or len(en.split()) < 5 \
                    or not en[:1].isupper():
                bad["例句不完整"].append(en[:50])
            else:
                marked = p07.bold_words(en, full)
                want = [w for w in re.split(r"[\s/]+", full[0])
                        if len(w) > 2 and w.lower() not in PLACE]
                miss = [w for w in want
                        if f"<b>" not in marked or w.lower()[:4] not in
                        " ".join(re.findall(r"<b>(.*?)</b>", marked)).lower()]
                if want and len(miss) > len(want) / 2:
                    bad["例句加粗不全"].append(f"{full[0]} → {marked[:56]}")
    return bad


def main():
    rows = rows_of()
    done = [r for r in rows if r[5]]
    todo = [r for r in rows if not r[5]]
    for label, part in (("已校对", done), ("未校对", todo)):
        bad = check(part)
        total = sum(len(v) for v in bad.values())
        print(f"\n【{label}】{len(part)} 行，问题 {total} 处"
              f"（{total / max(len(part), 1):.2f} 处/行）")
        for name, items in bad.items():
            if not items:
                continue
            print(f"  {name}: {len(items)}")
            if label == "已校对":
                for x in items[:3]:
                    print(f"      {x}")


if __name__ == "__main__":
    main()
