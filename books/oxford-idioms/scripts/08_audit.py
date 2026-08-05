"""Pass 08: 对成品做确定性校验，只报数字和样例。

查四件事：
1. 中文解释缺失、或混进了英文；
2. 例句缺英文或缺中文翻译；
3. 例句里没出现习语的核心词（模型跑题或换了别的说法）；
4. 同一个单词下面出现重复的习语。

Usage: 08_audit.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CJK = re.compile(r"[\u4e00-\u9fff]")
# 习语里的占位词，不能拿它们判断例句是否对得上
STOP = {"sb", "sth", "sb's", "sth's", "one", "one's", "your", "yours", "you",
        "the", "a", "an", "to", "of", "in", "on", "at", "for", "with", "and",
        "or", "be", "is", "are", "was", "were", "do", "does", "did", "have",
        "has", "had", "not", "no", "it", "its", "that", "this", "as", "so",
        "etc", "my", "his", "her", "their", "our", "me", "him", "them", "us",
        "up", "out", "off", "down", "over", "into", "from", "by", "about"}


def keywords(idiom):
    t = re.sub(r"\([^)]*\)", " ", idiom)         # 去掉 (informal) 之类
    t = t.replace("ˈ", "").replace("ˌ", "")
    # 习语里常有 `give/put`、`bad, tall, etc.` 这样的可替换成分，只要例句用上
    # 任意一个实词就算对上；只挑最长的两个词会把大量正确例句误判成跑题
    return [w for w in re.findall(r"[a-zA-Z']+", t.lower())
            if w not in STOP and len(w) > 2]


def main():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p07", os.path.join(os.path.dirname(os.path.abspath(__file__)), "07_render.py"))
    p07 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p07)

    book = json.load(open(os.path.join(DATA, "idioms.json")))
    cache = json.load(open(os.path.join(DATA, "cache.json")))
    problems = {"缺中文解释": [], "解释混英文": [], "例句不全": [],
                "例句没用上习语": []}
    deduped = []
    idx = checked = 0
    for h in book:
        seen = set()
        for it in h["idioms"]:
            rec = cache.get(str(idx))
            idx += 1
            if not rec:
                continue
            idiom, cn = rec["i"], rec["cn"]
            # 跟 07_render 用同一套过滤，校验的才是成品而不是中间数据
            key = re.sub(r"[^a-z]", "", idiom.lower())
            if not key or p07.junk(idiom):
                continue
            if key in seen:                  # 渲染时已自动去掉，只做统计
                deduped.append(f"{h['word']} / {idiom}")
                continue
            seen.add(key)
            en, _, cn_ex = rec["e"].partition("  ")
            tag = f"{h['word']} / {idiom}"
            checked += 1

            if not CJK.search(cn):
                problems["缺中文解释"].append(tag)
            elif re.search(r"[a-zA-Z]{4,}", cn):
                problems["解释混英文"].append(tag)
            if not re.search(r"[A-Za-z]{2,}", en) or not CJK.search(cn_ex):
                problems["例句不全"].append(tag)
            else:
                low = en.lower()
                kw = keywords(idiom)
                if kw and not any(k[:4] in low for k in kw):
                    problems["例句没用上习语"].append(tag)

    total = sum(len(v) for v in problems.values())
    print(f"校验成品 {checked} 条，有问题 {total} 条")
    for name, items in problems.items():
        print(f"  {name}: {len(items)}")
        for x in items[:3]:
            print(f"      {x}")
    print(f"  （另有 {len(deduped)} 条重复条目在渲染时已自动去掉，不计入问题）")


if __name__ == "__main__":
    main()
