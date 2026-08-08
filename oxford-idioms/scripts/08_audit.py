"""Pass 08: 对成品做确定性校验，只报数字和样例。

查的就是 07_render 渲染出来的那些行（共用它的 final_rows），不是中间数据。

1. 中文解释缺失、或混进了英文；
2. 例句缺英文或缺中文翻译；
3. 例句里没出现习语的实词（模型跑题或换了别的说法）；
4. 条目看着还是残片（以虚词收尾、没能拼回去的断行）；
5. 例句英文的字面质量：拼不出来的词、字母数字混搭、句中无故大写、标点后缺空格。
   第 5 类是清理管线的看门狗——改过 10_clean_ex.py 就必须跑一遍这里。
   历史教训：一条 `\\b(we)(ll|ve|re)\\b → we'll` 的规则把全书 449 处 were
   改成了 we're，肉眼抽查没看出来，是这类计数把它抓出来的。

## 交付前必须全部跑到 0 的七条（用户定的，别删别放宽）

| # | 项 | 判据 |
|---|---|---|
| 1 | 内容正确性 | `g00d`、`100k`、`l` 认成 `1`、单词截断这类低级 OCR 错，一个不许有 |
| 2 | 字号合理 | 格子**先靠折行填满，放不下才降字号**；不许留大片空白却把字缩小 |
| 3 | 一致性 | 习语 / 解释 / 例句必须是同一条，不许张冠李戴 |
| 4 | 表格线 | 内外框齐全清晰，不出框、不缺线、不重线（13_pdf.py 那边保证） |
| 5 | 无空格子 | 四列都不许空；星级没打到分的用中位数补 |
| 6 | 例句加粗 | 例句里的习语**整体**加粗，虚词、助词、连词一个都不能跳 |
| 7 | 闭环 | 修完重新跑这个脚本贴数字，收敛才收工。「已修未验证」不算做完 |

第 8 条是给自己的：一轮不超过 10 分钟，不重跑大规模 OCR，
优先拿现成的 `data/*.json`、`out/*.md` 推理。

Usage: 08_audit.py
"""
import importlib.util
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CJK = re.compile(r"[\u4e00-\u9fff]")
NUMERIC = re.compile(r"^[£$€]?\d[\d,./]*(st|nd|rd|th|s|k|m|bn|am|pm)?$", re.I)
HASDIGIT = re.compile(r"[A-Za-z’']*\d[A-Za-z’'\d]*")
NOSPACE = re.compile(r"[a-z][,;](?=[a-zA-Z])")        # 逗号后缺空格
# 习语里的占位词，不能拿它们判断例句是否对得上
STOP = {"sb", "sth", "sb's", "sth's", "one", "one's", "your", "yours", "you",
        "the", "a", "an", "to", "of", "in", "on", "at", "for", "with", "and",
        "or", "be", "is", "are", "was", "were", "do", "does", "did", "have",
        "has", "had", "not", "no", "it", "its", "that", "this", "as", "so",
        "etc", "my", "his", "her", "their", "our", "me", "him", "them", "us",
        "up", "out", "off", "down", "over", "into", "from", "by", "about"}

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


p07 = _load("p07", "07_render.py")
p10 = _load("p10", "10_clean_ex.py")     # 借它的 isword 做拼写判据，两处口径一致
# 两个模块是分别 load 的，各有各的实例，得再灌一次不规则动词表
p10.IRREG = p07.IRREG


def keywords(idiom):
    t = re.sub(r"\([^)]*\)", " ", idiom)         # 去掉 (informal) 之类
    t = t.replace("ˈ", "").replace("ˌ", "")
    # 习语里常有 `give/put`、`bad, tall, etc.` 这样的可替换成分，只要例句用上
    # 任意一个实词就算对上；只挑最长的两个词会把大量正确例句误判成跑题
    return [w for w in re.findall(r"[a-zA-Z']+", t.lower())
            if w not in STOP and len(w) > 2]


def main():
    book, cache = p07.load()
    rows, joined, dropped, made_up, fixed, cross, folded = p07.final_rows(book, cache)
    rows = [list(r) for r in rows]                  # 跟渲染走同一条路
    rows, from_book = p07.with_book_examples(rows)
    rows, moved = p07.regroup(rows)
    rows, recovered = p07.append_lost(rows)
    scores = p07.load_scores()                      # 打分兜的最后一遍残片过滤
    rows = [list(r) for r in rows]
    for r in rows:
        r[1] = p07.tidy_idiom(r[1])          # 跟渲染同一条路
    rows = [r for r in rows
            if not p07.fragment(r[1], scores.get(re.sub(r"[^a-z]", "",
                                                        r[1].lower())))]
    problems = {"缺中文解释": [], "解释混英文": [], "例句不全": [],
                "例句没用上习语": [], "条目像残片": [], "例句有拼不出的词": [],
                "例句字母数字混搭": [], "例句句中无故大写": [], "例句标点后缺空格": [],
                "中译断在半句": [], "格子空着": [], "例句没加粗": []}
    word = ""
    for w, idiom, cn, en_ex, cn_ex, *_ in rows:
        word = w or word
        tag = f"{word} / {idiom}"
        # 拼写只查原书例句——它才可能被 OCR 认坏。自拟例句是模型写的，
        # 里面的 retiled、hotfooted、ha'porth 都是正经词，只是语料频率低
        if "（自拟）" not in cn_ex:
            # 条目自带的外来语生词（`ad infiˈnitum`、`je ne sais quoi`）频率也极低，
            # 但例句用上它们是对的，所以先把条目里出现过的词摘掉再判
            own = set(re.findall(r"[a-z’']+",
                                 idiom.lower().replace("ˈ", "").replace("ˌ", "")))
            bad = [x for x in re.findall(r"\b[a-z][a-z’']*\b", en_ex)
                   if x not in own and not p10.isword(x)]
            if bad:
                problems["例句有拼不出的词"].append(f"{tag} ← {' '.join(bad[:3])}")
        if any(not NUMERIC.match(x) for x in HASDIGIT.findall(en_ex)):
            problems["例句字母数字混搭"].append(tag)
        # 判据直接用清理管线那一份。这里另写一条正则时 `Labour Party` 的 Party
        # 会被误报——单看正则不知道左右两边还有没有别的大写词
        if p10.lower_midcaps(en_ex) != en_ex:
            problems["例句句中无故大写"].append(tag)
        if NOSPACE.search(en_ex):
            problems["例句标点后缺空格"].append(tag)
        # 中译断在半句（`信不信由你，我刚在比赛中赢得`）。光看汉字数放得过去，
        # 得看句末标点。自拟例句的中译带「（自拟）」后缀，剥掉再判
        plain = cn_ex.replace("（自拟）", "").rstrip()
        if plain and not plain.endswith(("。", "！", "？", "”", "）")):
            problems["中译断在半句"].append(tag)
        # 空格子：读者只会当成漏印。星级列没打到分的也要给中位数补上
        if not (idiom.strip() and cn.strip() and en_ex.strip() and cn_ex.strip()):
            problems["格子空着"].append(tag)
        # 例句里的习语要整体加粗，虚词也包进去
        if en_ex.strip() and p07.bold_idiom(en_ex, idiom) == en_ex:
            problems["例句没加粗"].append(tag)
        if not CJK.search(cn):
            problems["缺中文解释"].append(tag)
        elif re.search(r"[a-zA-Z]{4,}", cn):
            problems["解释混英文"].append(tag)
        if not re.search(r"[A-Za-z]{2,}", en_ex) or not CJK.search(cn_ex):
            problems["例句不全"].append(tag)
        elif not p10.uses_idiom(en_ex, idiom):
            # 判据直接用 10_clean_ex 那一份，两处口径必须一致——各写一套的时候，
            # 这边比那边严，报出来 26 条其实全是 lose your life → lost their lives
            # 这类正常的屈折变化
            problems["例句没用上习语"].append(tag)
        # 判残片不能只看「以虚词收尾」——英语习语本来就有很多以介词结尾的
        # （`to beˈgin with`、`in the region of`、`a rod/stick to ˈbeat sb with`），
        # with / of / that 收尾一律放行（`ˈsomething like that` 也是正经条目），
        # 剩下的 the / a / and 收尾才是真断行
        if re.search(r"\b(the|a|an|and|or|by|your|his|her|their|"
                     r"its|our|my)$", idiom.strip(), re.I):
            problems["条目像残片"].append(tag)

    total = sum(len(v) for v in problems.values())
    print(f"校验成品 {len(rows)} 条，有问题 {total} 条（{total/len(rows):.1%}）")
    for name, items in problems.items():
        print(f"  {name}: {len(items)}")
        for x in items[:3]:
            print(f"      {x}")
    print(f"  （渲染时已拼回断行 {joined} 条、去掉重复和残片 {dropped} 条、"
          f"剔除模型猜出来的 {made_up} 条、纠正关键词 {fixed} 个、跨词条重复 {cross} 条、收拢后半截 {folded} 条、捞回 {recovered} 条、改挂 {moved} 条）\n"
          f"  例句：原书 {from_book} 条，其余自拟")


if __name__ == "__main__":
    main()
