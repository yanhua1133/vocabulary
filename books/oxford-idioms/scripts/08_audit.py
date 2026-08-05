"""Pass 08: 对成品做确定性校验，只报数字和样例。

查的就是 07_render 渲染出来的那些行（共用它的 final_rows），不是中间数据。

1. 中文解释缺失、或混进了英文；
2. 例句缺英文或缺中文翻译；
3. 例句里没出现习语的实词（模型跑题或换了别的说法）；
4. 条目看着还是残片（以虚词收尾、没能拼回去的断行）。

Usage: 08_audit.py
"""
import importlib.util
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CJK = re.compile(r"[\u4e00-\u9fff]")
# 习语里的占位词，不能拿它们判断例句是否对得上
STOP = {"sb", "sth", "sb's", "sth's", "one", "one's", "your", "yours", "you",
        "the", "a", "an", "to", "of", "in", "on", "at", "for", "with", "and",
        "or", "be", "is", "are", "was", "were", "do", "does", "did", "have",
        "has", "had", "not", "no", "it", "its", "that", "this", "as", "so",
        "etc", "my", "his", "her", "their", "our", "me", "him", "them", "us",
        "up", "out", "off", "down", "over", "into", "from", "by", "about"}

spec = importlib.util.spec_from_file_location("p07", os.path.join(HERE, "07_render.py"))
p07 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p07)


def keywords(idiom):
    t = re.sub(r"\([^)]*\)", " ", idiom)         # 去掉 (informal) 之类
    t = t.replace("ˈ", "").replace("ˌ", "")
    # 习语里常有 `give/put`、`bad, tall, etc.` 这样的可替换成分，只要例句用上
    # 任意一个实词就算对上；只挑最长的两个词会把大量正确例句误判成跑题
    return [w for w in re.findall(r"[a-zA-Z']+", t.lower())
            if w not in STOP and len(w) > 2]


def main():
    book, cache = p07.load()
    rows, joined, dropped, made_up = p07.final_rows(book, cache)
    problems = {"缺中文解释": [], "解释混英文": [], "例句不全": [],
                "例句没用上习语": [], "条目像残片": []}
    word = ""
    for w, idiom, cn, en_ex, cn_ex, _ in rows:
        word = w or word
        tag = f"{word} / {idiom}"
        if not CJK.search(cn):
            problems["缺中文解释"].append(tag)
        elif re.search(r"[a-zA-Z]{4,}", cn):
            problems["解释混英文"].append(tag)
        if not re.search(r"[A-Za-z]{2,}", en_ex) or not CJK.search(cn_ex):
            problems["例句不全"].append(tag)
        else:
            low = en_ex.lower()
            kw = keywords(idiom)
            if kw and not any(k[:4] in low for k in kw):
                problems["例句没用上习语"].append(tag)
        if p07.DANGLING.search(idiom.strip()):
            problems["条目像残片"].append(tag)

    total = sum(len(v) for v in problems.values())
    print(f"校验成品 {len(rows)} 条，有问题 {total} 条（{total/len(rows):.1%}）")
    for name, items in problems.items():
        print(f"  {name}: {len(items)}")
        for x in items[:3]:
            print(f"      {x}")
    print(f"  （渲染时已拼回断行 {joined} 条、去掉重复和残片 {dropped} 条、"
          f"剔除模型猜出来的 {made_up} 条）")


if __name__ == "__main__":
    main()
