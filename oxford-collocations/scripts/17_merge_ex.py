"""Pass 17: 把子 agent 自拟的例句并进 data/cache.json，供 07_render 回填。

写进 cache 而不是另起一个文件，是因为渲染那边本来就按 `词头||搭配` 查 cache，
两种来源（校对过的 / 自拟的）走同一条路，不用在渲染里加分支。

每条都要过校验，不合格的宁可不要——空着还能再补，印错了就得整本重排：
- 键必须对得上现有的行
- 例句里必须真的用上这条搭配（允许屈折变化）
- 长度要排得进两行（半角宽 ≤ 170）
- 中译必须是中文、且以句末标点收尾

Usage: 17_merge_ex.py
"""
import glob
import importlib.util
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
WORK = os.path.join(ROOT, "work", "makeex")
CJK = re.compile(r"[\u4e00-\u9fff]")
# 判「例句用上搭配没有」时要跳过的词：代词、物主代词、虚词
SKIP_MATCH = {"the", "sth", "sb", "and", "for", "with", "into", "your", "his",
              "her", "their", "its", "our", "yours", "one", "ones", "you",
              "they", "them", "that", "this", "these", "those", "not", "etc"}
# 不规则动词：条目写原形，例句里是变位形式
IRREG = {}
for _b, _f in {"be": "is are was were been", "have": "has had", "do": "does did",
               "go": "goes went gone", "get": "gets got", "take": "takes took",
               "make": "makes made", "give": "gives gave", "come": "comes came",
               "keep": "keeps kept", "leave": "leaves left", "lose": "loses lost",
               "pay": "pays paid", "find": "finds found", "hold": "holds held",
               "run": "runs ran", "bring": "brings brought", "buy": "buys bought",
               "catch": "catches caught", "feel": "feels felt", "sell": "sells sold",
               "send": "sends sent", "win": "wins won", "draw": "draws drew",
               "break": "breaks broke broken", "speak": "speaks spoke",
               "stand": "stands stood", "strike": "strikes struck",
               "teach": "teaches taught", "think": "thinks thought",
               "meet": "meets met", "lead": "leads led", "set": "sets",
               "put": "puts", "cut": "cuts", "let": "lets"}.items():
    IRREG[_b] = tuple((_b + " " + _f).split())
# 语域/用法标签：词典的标记，例句里本来就不该出现，别拿它去卡例句
LABEL = {"ame", "bre", "name", "esp", "especially", "also", "often", "usually",
         "sometimes", "figurative", "literal", "informal", "formal",
         "approving", "disapproving", "note", "both", "rare"}


def strip_labels(coll):
    """去掉 (AmE)、(esp. BrE)、(also figurative) 这类纯标签的括号。

    括号里只要有一个实词就整段留着——(behind)、(with sth) 是搭配的一部分，
    不能一刀切把括号全删了。
    """
    def drop(m):
        ws = re.findall(r"[a-z]{3,}", m.group(1).lower())
        return "" if ws and all(w in LABEL for w in ws) else m.group(0)

    return re.sub(r"\(([^)]*)\)", drop, coll)


def usable(coll, en, zh):
    if not en or not zh or not CJK.search(zh):
        return False
    if not (6 <= len(en.split()) <= 24):
        return False
    if sum(2 if ord(c) > 0x2e80 else 1 for c in en + zh) > 170:
        return False
    if not en[0].isupper() or not en.rstrip().endswith((".", "!", "?", '"', "”")):
        return False
    if CJK.search(en):
        return False
    # 搭配的实词要出现在例句里，按词干比（provide → provided）。
    # 三处必须放宽，否则会把大量好例句判掉：
    # ① 人称和物主代词——条目写 `a spring in your step`，例句写 his step
    # ② 不规则动词——条目 have，例句 has / had，词干比不出来
    # ③ 只要求**七成**实词命中：条目里常带 (usually steakhouse) 这类附注词
    low = en.lower()
    core = [w for w in re.findall(r"[a-z]{3,}", strip_labels(coll).lower())
            if w not in SKIP_MATCH]
    if not core:
        return True
    hit = sum(1 for w in core
              if w[:max(3, len(w) - 2)] in low
              or any(f in low for f in IRREG.get(w, ())))
    return hit >= max(1, round(len(core) * 0.7))


def main():
    spec = importlib.util.spec_from_file_location(
        "p16", os.path.join(HERE, "16_make_ex.py"))
    p16 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p16)
    spec2 = importlib.util.spec_from_file_location(
        "p07", os.path.join(HERE, "07_render.py"))
    p07 = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(p07)

    book, cache = p07.load()
    # 键 → 这一格的搭配原文，用来校验例句有没有用上它
    want = {}
    for word, _pos, full, _cn, en, _zh, _d, key in p07.iter_rows(book, cache):
        if not en.strip():
            want[key] = full[0]

    added = bad = 0
    for f in sorted(glob.glob(os.path.join(WORK, "*.out.json"))):
        for it in json.load(open(f)).get("ex", []):
            k, en, zh = it.get("k"), (it.get("en") or "").strip(), \
                (it.get("zh") or "").strip()
            if k not in want or not usable(want[k], en, zh):
                bad += 1
                continue
            if not zh.endswith(("。", "！", "？", "”", "）")):
                zh += "。"
            old = cache.get(k) or {}
            old["ex"] = f"{en}  {zh}（自拟）"
            old.setdefault("cn", "")
            cache[k] = old
            added += 1
    # 顺带并入补写的中文解释（work/makecn/all.out.json）
    cnf = os.path.join(ROOT, "work", "makecn", "all.out.json")
    cn_added = 0
    if os.path.exists(cnf):
        for it in json.load(open(cnf)).get("cn", []):
            k, v = it.get("k"), (it.get("cn") or "").strip()
            # 解释必须是纯中文，混进英文的是模型把例句抄了进来
            if not v or not CJK.search(v) or re.search(r"[A-Za-z]{3,}", v):
                continue
            old = cache.get(k) or {}
            if old.get("cn"):
                continue
            old["cn"] = v
            old.setdefault("ex", "")
            cache[k] = old
            cn_added += 1
    json.dump(cache, open(os.path.join(DATA, "cache.json"), "w"),
              ensure_ascii=False, indent=0)
    print(f"并入自拟例句 {added} 条，丢弃 {bad} 条；还差 {len(want) - added} 条")
    print(f"并入补写的中文解释 {cn_added} 条")


if __name__ == "__main__":
    main()
