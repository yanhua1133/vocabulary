"""Pass 07: 渲染最终成品 → out/牛津习语词典.md。

四列：**单词 / 习语 / 中文解释 / 例句**。一个单词下面的若干条习语连排在一起，
单词列只在第一行写一次。

条目文本、中文释义、例句都优先取 data/cache.json（子 agent 校对/重写过的），
没有缓存就退回 data/idioms.json 里从扫描件抽出来的原文。

渲染时还做三件收尾：拼回被排版断成两条的习语、去掉重复条目、扔掉音标残片。
这三件都放在这一步而不是回头改 02——缓存是按 data/idioms.json 的序号存的，
上游一动序号就全错位，7600 条得重跑。

Usage: 07_render.py
"""
import difflib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")
# 关键词行的音标偶尔会被切成独立一行，混进条目里（`ˈa:rmtʃer; a:rmˈtʃer/`）
IPA_JUNK = re.compile(r"(;.*/|/\s*$|^[^A-Za-z]*[a-z]:)")
# 只有音标里才会出现的字符，用来认出「关键词 + 音标」那种整行
IPA_CHARS = re.compile(r"/[^/]*[ɑɒəɜɪʊʌæŋʃʒθðːˑ][^/]*/|/[^/]*[a-z]:[^/]*/")
# 条目在栏底被断成两行、断点又不在括号里时，02 的合并逻辑接不上，就拆成了两条
# （`…half a dozen of the` + `ˈother (saying)`）。下面这些虚词绝不可能是习语的
# 结尾，拿来当断行信号很安全——注意别把 in/on/out/up 算进来，
# `keep your ˈhand in` 本身就是完整条目。
DANGLING = re.compile(r"\b(the|a|an|of|and|or|to|for|with|from|that|by|as|"
                      r"your|his|her|their|its|our|my)$", re.I)


def cell(s):
    return (s or "").replace("|", "／").replace("\n", " ").strip()


def junk(idiom):
    if IPA_JUNK.search(idiom) and " " not in idiom.strip(" /"):
        return True
    # 带音标的关键词行整行混进来（`labour (BrE) (AmE labor) /ˈleɪbə(r)/`）。
    # 剥掉音标和括号后只剩一两个词的就是关键词；`je ne sais quoi /…/ (from French)`、
    # `a ˌsine qua ˈnon /…/` 这类外来语条目本来就带音标，词数多，留着。
    if IPA_CHARS.search(idiom):
        bare = re.sub(r"/[^/]*/|\([^)]*\)|[;:]", " ", idiom)
        return len(re.findall(r"[A-Za-zÀ-ÿ'-]+", bare)) <= 2
    return False


def fabricated(raw, final):
    """模型把 OCR 残片「救」成了另一条习语——这种要扔掉。

    有个子 agent 报告说，它遇到例句碎片、词源框、乱码时（`In this sense, ˈcheese'
    comes from the Urdu`、`anyway?`），会按关键词猜一条该词条下真实存在的习语填上
    （猜成了 `a ˌbig ˈwheel (informal)`）。猜得对不对无从验证，来源行本身也不是条目，
    所以一律剔除。

    判据是两者有没有实质性的公共内容：模型把残片**补全**（`ˈjudgment)` →
    `against your better ˈjudgement…`）或从例句里**还原**出条目（`the biter bit —
    she'd tried…` → `the biter ˈbit`）时，公共子串都很长，这些要留。
    """
    a, b = (re.sub(r"[^a-z]", "", x.lower()) for x in (raw, final))
    if not a or not b:
        return False
    m = difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
    return m.size < min(6, len(a), len(b))


STEM = re.compile(r"(ies|es|s|ing|ed)$")
# 判断关键词时要跳过的虚词
FUNC = {"the", "a", "an", "of", "to", "in", "on", "at", "for", "with", "and",
        "or", "be", "is", "are", "was", "were", "do", "does", "did", "have",
        "has", "had", "not", "no", "it", "its", "you", "your", "sb", "sth",
        "sbs", "sths", "one", "ones", "as", "so", "that", "this", "up", "out",
        "off", "down", "over", "into", "from", "by", "about", "all", "etc",
        "my", "his", "her", "their", "our", "me", "him", "them", "us", "if"}


def bare(t):
    return re.sub(r"[ˈˌ]", "", t).lower()


def fix_group_word(word, idioms):
    """整组条目都不含这个关键词时，说明关键词认错了或整组挂错了地方。

    牛津的条目一定含它所属的关键词，所以：
    - 组里有跟它形近的词 → 是 OCR 错字（`albsence` → `absence`），照组里的写法改；
    - 组里每一条都含同一个实词 → 那才是真关键词（关键词行被漏识别，条目挂到了
      上一个关键词底下）；
    - 都不满足就别猜，原样留着，交给 08_audit 报出来。
    """
    stem = STEM.sub("", word.lower())
    bodies = [bare(t) for t in idioms]
    if any(stem and stem in b for b in bodies):
        return word
    words = set(re.findall(r"[a-z']+", " ".join(bodies)))
    close = difflib.get_close_matches(word.lower(), words, n=1, cutoff=0.75)
    if close:
        return close[0]
    common = None
    for w in re.findall(r"[a-z']+", bodies[0]):
        if w in FUNC or len(w) < 3:
            continue
        if all(STEM.sub("", w) in b for b in bodies):
            common = w
            break
    return common or word


def is_continuation(nxt):
    """下一条看着像上一条的后半截：短，且以小写词或重音符号起头。"""
    n = (nxt or "").strip()
    return bool(n) and len(n) < 45 and (n[0] in "ˈˌ" or n[0].islower())


def build(book, cache):
    """按 data/idioms.json 的顺序摊平成 (单词, 条目, 释义, 例句原文) 列表。"""
    flat, idx = [], 0
    for hid, h in enumerate(book):           # hid 用来分组：同名的两个词头是两组
        for it in h["idioms"]:
            rec = cache.get(str(idx))
            idx += 1
            body = bool(it["cn"] or it["ex_en"])   # 原书这条底下有没有释义正文
            if rec:
                flat.append([hid, h["word"], rec["i"], rec["cn"], rec["e"], True,
                             it["idiom"], body])
            else:
                ex = f"{it['ex_en']}  {it['ex_cn']}" if it["ex_cn"] else it["ex_en"]
                flat.append([hid, h["word"], it["idiom"], it["cn"], ex, False,
                             it["idiom"], body])
    return flat


def load():
    book = json.load(open(os.path.join(DATA, "idioms.json")))
    cache_path = os.path.join(DATA, "cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    return book, cache


def final_rows(book, cache):
    """成品的每一行：(单词, 条目, 中文解释, 英文例句, 例句中译, 是否校对过)。

    校验脚本也用这个函数，保证查的就是成品本身，不是中间数据。
    """
    flat = build(book, cache)

    # 1) 拼回断成两条的习语；释义和例句取后半截那条的——子 agent 是按完整习语写的，
    #    后半截带着 (saying) 之类的标签，信息更全
    merged, joined, i = [], 0, 0
    while i < len(flat):
        cur = flat[i]
        nxt = flat[i + 1] if i + 1 < len(flat) else None
        if (nxt and cur[0] == nxt[0] and DANGLING.search(cur[2].strip())
                and is_continuation(nxt[2])):
            merged.append([cur[0], cur[1], f"{cur[2].strip()} {nxt[2].strip()}",
                           nxt[3] or cur[3], nxt[4] or cur[4], cur[5],
                           cur[6] + " " + nxt[6], cur[7] or nxt[7]])
            joined += 1
            i += 2
            continue
        merged.append(cur)
        i += 1

    # 2) 同一个单词下的重复条目只留一条，音标残片直接扔掉
    rows, dropped, made_up, last_hid = [], 0, 0, None
    seen = set()
    for hid, word, idiom, cn, ex, from_cache, raw, body in merged:
        if hid != last_hid:
            seen = set()
        key = re.sub(r"[^a-z]", "", idiom.lower())
        if not key or key in seen or junk(idiom):
            dropped += 1
            continue
        if fabricated(raw, idiom):
            made_up += 1
            continue
        seen.add(key)
        en_ex, _, cn_ex = ex.partition("  ")
        rows.append([word if hid != last_hid else "",
                     idiom, cn, en_ex, cn_ex, from_cache, body])
        last_hid = hid

    # 关键词是按组给的，得先把整组收齐再判断这个词对不对
    groups, cur = [], None
    for i, r in enumerate(rows):
        if r[0]:
            cur = (i, [])
            groups.append(cur)
        if cur:
            cur[1].append(r[1])
    fixed = 0
    for i, idioms in groups:
        better = fix_group_word(rows[i][0], idioms)
        if better != rows[i][0]:
            rows[i][0] = better
            fixed += 1

    # 同一条习语挂在两个关键词下（一处是正文，另一处是交叉引用被还原成了条目）。
    # 保留原书底下有释义正文的那条——交叉引用行下面是空的
    best = {}
    for i, r in enumerate(rows):
        k = re.sub(r"[^a-z]", "", r[1].lower())
        if k not in best or (r[6] and not rows[best[k]][6]):
            best[k] = i
    kept, cross = [], 0
    for i, r in enumerate(rows):
        k = re.sub(r"[^a-z]", "", r[1].lower())
        if best[k] != i:
            cross += 1
            if r[0]:                     # 组首被删掉时，单词标记交给下一行
                for j in range(i + 1, len(rows)):
                    if best[re.sub(r"[^a-z]", "", rows[j][1].lower())] == j:
                        if not rows[j][0]:
                            rows[j][0] = r[0]
                        break
            continue
        kept.append(tuple(r[:6]))
    return kept, joined, dropped, made_up, fixed, cross


def main():
    book, cache = load()
    rows, joined, dropped, made_up, fixed, cross = final_rows(book, cache)
    filled = sum(1 for r in rows if r[5])

    os.makedirs(OUT, exist_ok=True)
    words = sum(1 for r in rows if r[0])
    lines = ["# 牛津习语词典\n",
             f"\n{words} 个单词，{len(rows)} 条习语。"
             f"其中 {filled} 条（{filled/max(len(rows),1):.1%}）的释义和例句经过校对重写。\n",
             "\n<table>",
             "<thead><tr><th>单词</th><th>习语</th><th>中文解释</th>"
             "<th>例句</th></tr></thead>"]
    for word, idiom, cn, en_ex, cn_ex, _ in rows:
        w = f"<b>{cell(word)}</b>" if word else ""
        ex = f"{cell(en_ex)}<br>{cell(cn_ex)}" if cn_ex else cell(en_ex)
        lines.append(f"<tr><td>{w}</td><td>{cell(idiom)}</td>"
                     f"<td>{cell(cn)}</td><td>{ex}</td></tr>")
    lines.append("</table>\n")
    p = os.path.join(OUT, "牛津习语词典.md")
    open(p, "w").write("\n".join(lines))
    print(f"{words} 个单词，{len(rows)} 条习语（校对过 {filled} 条）")
    print(f"  拼回断行条目 {joined} 条，去掉重复/音标残片 {dropped} 条，"
          f"剔除模型猜出来的 {made_up} 条，纠正关键词 {fixed} 个，"
          f"合并跨词条重复 {cross} 条")
    print(p)


if __name__ == "__main__":
    main()
