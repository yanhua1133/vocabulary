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
import importlib.util
import json
import os
import re

_spec = importlib.util.spec_from_file_location(
    "p10", os.path.join(os.path.dirname(os.path.abspath(__file__)), "10_clean_ex.py"))
_p10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p10)
polish, polish_cn = _p10.polish, _p10.polish_cn   # 两种来源共用同一套字面收尾
# IRREG 在本文件下方定义，import 完再回灌给 _p10（uses_idiom 也要用同一张表）

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
# 习语常见的起手词，用来判断切掉例句碎片后要往前捡回几个词
IDIOM_HEAD = set("be a an the not no your his her its our their sb's sth's "
                 "one's in on at of".split())
# 例句碎片粘在条目前面的两种形态。判据必须窄，不然会切掉正经谚语
# （`when the cat's aˈway the mice will ˈplay`、`the goose that lays the golden ˈeggs`）：
# 只认「限定句」（`…ed that`、`which is`）和「整条以分词分句起头」两种
PROSE_HEAD = (re.compile(r"^.{6,}?(?:\b\w+ed that\b|\bwhich is\b)\s+"),
              re.compile(r"^(?!some|any|no|every|during)\w+ing\b.{6,}?"
                         r"\b(?:when|that)\b\s+"))


def stars(n):
    """0-5 的分打成星：★ 一颗，☆ 半颗。跟 GRE3000 一个写法，最低半颗星。"""
    try:
        v = max(0.5, min(5.0, round(float(n) * 2) / 2))
    except (TypeError, ValueError):
        return ""
    full = int(v)
    return "★" * full + ("☆" if v - full >= 0.5 else "")


# 语域标签。带标签的一定是正经条目，哪怕它冷僻到没人用
REGISTER = re.compile(r"\((BrE|AmE|informal|formal|spoken|saying|literary|"
                      r"humorous|disapproving|approving|old-fashioned|old use|"
                      r"slang|written|especially|figurative|taboo|law|"
                      r"AustralE|NZE|New Zealand)", re.I)


def fragment(idiom, score):
    """靠打分结果兜最后一遍残片。

    打分的子 agent 顺手提供了一个很好的信号：被误切进来的释义正文和例句碎片，
    常用度一律打到最低。但光看分会误杀真·生僻习语（`like ˈbilly-o`、
    `the/a ˌcurate's ˈegg`），所以再加两个条件——**没有重音符号**、
    **没有语域标签**。三条同时满足的 41 条里，只有 `now… now…` 一条是错杀。
    """
    # NOTE 框里的说明句。它们常带 OCR 误认的重音符号，躲得过下面那三条，
    # 只能靠措辞认：`This phrase originated in the 1940s as ˈthe`、
    # `in which the child has to say the word ˈuncle`。判据要窄——
    # 放宽到 this/these 开头会误杀 `these things are ˌsent to ˈtry us` 这种真谚语
    if re.search(r"\b(originated|refers to|is often used)\b", idiom, re.I) \
            or re.match(r"^in which\b", idiom, re.I):
        return True
    # 右括号比左括号多 = 前半截丢了（`ˈfavor of sb/sth)`、
    # `usually asleep at the ˈswitch) (informal)`）。finalize 会补右括号，
    # 所以反过来左多右少不会出现，这条判据很安全
    if idiom.count(")") > idiom.count("("):
        return True
    # `> Investors are wary of getting into bed with an get out of bed on the
    # wrong ˈside` 这种，是正文碎片跟条目粘在一起了，开头那个 > 是原书的例句标记
    if idiom.lstrip().startswith((">", "◇", "»")):
        return True
    if not score or score.get("u", 9) > 1:
        return False
    return ("ˈ" not in idiom and "ˌ" not in idiom
            and not REGISTER.search(idiom))


def load_scores():
    path = os.path.join(DATA, "scores.json")
    return json.load(open(path)) if os.path.exists(path) else {}


def cell(s):
    return (s or "").replace("|", "／").replace("\n", " ").strip()


# 习语里的次要成分：语域标签，以及 (also …)/(or …) 这类变体写法
TAGS_RE = re.compile(
    r"(\((?:also|or)\s[^)]*\)"
    r"|\((?:especially |usually |also |or )?"
    r"(?:BrE|AmE|informal|formal|spoken|saying|literary|humorous|disapproving|"
    r"approving|old-fashioned|old use|slang|written|figurative|taboo|law|"
    r"AustralE|NZE)[^)]*\))")


def shrink_tags(idiom):
    """把习语后面的语域标签和 also 变体包起来，排 PDF 时用更小的字号。

    `against your better ˈjudgement (especially BrE) (AmE usually against your
    ˈjudgment)`、`get your ˈact together ◆ get sth/it toˈgether (informal)
    (also get/have your ˈshit together)` 这种，括号里的比习语本身还长。
    这些都是次要信息，缩小它们就能把整条压进两行，不用整体缩到看不清、
    也不用占第三行。

    注意要一次 sub 完，分两次包会产生嵌套 span、把后一个正则的匹配搞坏。
    """
    return TAGS_RE.sub(r'<span class="tag">\1</span>', idiom)


def glue_stress(t):
    """在重音符号后面插一个 word joiner，别让浏览器从这儿断行。

    ˈ ˌ 是修饰字母（Lm），Chrome 会把它当成可断点，于是排出
    `ˈ` 换行 `action stations` 这种——重音符号孤零零留在行尾，
    而且平白多出一行、把字号也连累得缩到看不清。

    别用 word joiner（U+2060）粘：那个字符在正文字体里没有字形，会触发字体回退，
    连带把 ˈ 本身渲染没了（排出来成了 `take ad vantage`）。用 nowrap 包着才稳。
    """
    return re.sub(r"([ˈˌ][A-Za-z'’-]+)", r'<span class="nw">\1</span>', t)


def strip_marker(idiom):
    """剥掉原书的提示前缀。`OPP` 是反义提示、`SYN` 是同义提示、`SEE` 是参见，
    它们印在条目前面，OCR 时会粘进条目文本里。"""
    return re.sub(r"^(OPP|SYN|SEE|NOTE)\s+", "", idiom.strip())


def junk(idiom):
    if IPA_JUNK.search(idiom) and " " not in idiom.strip(" /"):
        return True
    # 带音标的关键词行整行混进来（`labour (BrE) (AmE labor) /ˈleɪbə(r)/`）。
    # 剥掉音标和括号后只剩一两个词的就是关键词；`je ne sais quoi /…/ (from French)`、
    # `a ˌsine qua ˈnon /…/` 这类外来语条目本来就带音标，词数多，留着。
    if IPA_CHARS.search(idiom):
        stripped = re.sub(r"/[^/]*/|\([^)]*\)|[;:]", " ", idiom)
        return len(re.findall(r"[A-Za-zÀ-ÿ'-]+", stripped)) <= 2
    t = idiom.strip()
    # 没闭合的音标（`ˈa:rmtʃer; a:rmˈtʃer/`、`armour (BrE) (AmE armor) /ˈa:mə(r); AmE`）
    if re.search(r"[a-zA-Z]:", t) and ("/" in t or ";" in t):
        return True
    # 例句片段：大写起头的长句，且没有重音符号。习语哪怕大写起头也带 ˈ
    # （`Bob's your ˈuncle`、`God ˈknows`），例句正文不带
    if t[:1].isupper() and len(t) > 35 and "ˈ" not in t:
        return True
    return t.endswith("-")                   # 断词换行的正文残片


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


# 条目被排版断开、后半截只剩一串标签时的开头（`(AmE usually run ˈroughshod…`）。
# 只认这些词——`(up) in the ˈair`、`(not) at ˈall`、`(whether) by ˌaccident…`
# 都是原书就以括号开头的正经条目，不能一并吞掉
TAG_HEAD = re.compile(r"^\((AmE|BrE|also|informal|formal|especially|spoken|"
                      r"saying|usually|or)\b", re.I)
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
            src = str(idx - 1)                     # 用来回查原书例句
            if rec:
                flat.append([hid, h["word"], rec["i"], rec["cn"], rec["e"], True,
                             it["idiom"], body, src])
            else:
                ex = f"{it['ex_en']}  {it['ex_cn']}" if it["ex_cn"] else it["ex_en"]
                flat.append([hid, h["word"], it["idiom"], it["cn"], ex, False,
                             it["idiom"], body, src])
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
                           cur[6] + " " + nxt[6], cur[7] or nxt[7],
                           cur[8] if cur[7] else nxt[8]])
            joined += 1
            i += 2
            continue
        merged.append(cur)
        i += 1

    # 2) 同一个单词下的重复条目只留一条，音标残片直接扔掉
    rows, dropped, made_up, last_hid = [], 0, 0, None
    seen = {}
    for hid, word, idiom, cn, ex, from_cache, raw, body, src in merged:
        if hid != last_hid:
            seen = {}
        key = re.sub(r"[^a-z]", "", idiom.lower())
        if not key or junk(idiom):
            dropped += 1
            continue
        if fabricated(raw, idiom):
            made_up += 1
            continue
        if key in seen:
            # 同一条在组里出现两次时，留下**原书底下有正文**的那条。
            # 先入为主会出事：`a ˌbird in the ˈhand…` 被拆成两行、两半都补成了
            # 整条，前一半没正文；留下它，后面的去重又会因为它没正文把它删掉，
            # 整条习语就只剩交叉引用那个没有重音符号的版本了
            j = seen[key]
            if body and not rows[j][6]:
                en2, _, cn2 = ex.partition("  ")
                rows[j] = [rows[j][0], idiom, cn, en2, cn2, from_cache,
                           body, src]
            dropped += 1
            continue
        seen[key] = len(rows)
        en_ex, _, cn_ex = ex.partition("  ")
        rows.append([word if hid != last_hid else "",
                     idiom, cn, en_ex, cn_ex, from_cache, body, src])
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

    # 组内收尾：把只剩标签的后半截拼回前一条，删掉整条都被前一条包住的残片
    folded = 0
    keep = [True] * len(rows)
    prev = None
    for i, r in enumerate(rows):
        if r[0]:
            prev = i
            continue
        if prev is None:
            continue
        if TAG_HEAD.match(r[1].strip()):
            rows[prev][1] = f"{rows[prev][1].strip()} {r[1].strip()}"
            keep[i] = False
            folded += 1
            continue
        a, b = (re.sub(r"[^a-z]", "", x.lower()) for x in (r[1], rows[prev][1]))
        if a and a in b:
            # 两条内容重合时，留下**原书底下有正文**的那条。默认删后一条会出事：
            # `a ˌbird in the ˈhand…` 被拆成两行、两半都补成了整条，前一条没正文、
            # 后一条有；删了后一条，前一条又会在后面的去重里因为没正文被删，
            # 结果整条习语只剩下交叉引用那个没有重音符号的劣质版本
            drop = prev if (r[6] and not rows[prev][6]) else i
            keep[drop] = False
            folded += 1
            if drop == prev:
                rows[i][0] = rows[i][0] or rows[prev][0]
                prev = i
            continue
        prev = i
    rows = [r for r, ok in zip(rows, keep) if ok]

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
        kept.append(tuple(r[:8]))
    # 忽略括号标签后重合的，多半也是同一条挂了两处
    # （`beat/turn ˈswords into ˈploughshares (BrE)…` 同时挂在 plot 和 swords 下）。
    # 但只有在「一条有原书正文、另一条没有」时才敢删没正文的那条——
    # `in the ˈair` 和 `(up) in the ˈair` 两条都有正文，是两个词条，不能合。
    def core(t):
        return re.sub(r"[^a-z]", "", re.sub(r"\([^)]*\)", "", t).lower())

    bodies = {}
    for r in kept:
        bodies.setdefault(core(r[1]), set()).add(bool(r[6]))
    final, tagdup = [], 0
    for r in kept:
        if bodies.get(core(r[1])) == {True, False} and not r[6]:
            tagdup += 1
            continue
        final.append(r)
    return final, joined, dropped, made_up, fixed, cross + tagdup, folded


def regroup(rows):
    """把挂错关键词的条目改挂回去，顺带补出被漏识别的关键词。

    02 偶尔整行漏掉一个关键词（`all`、`iron`、`money` 在 data/book.json 里根本
    不存在），它底下的条目就顺延挂到了前一个关键词上——抽样验收时 60 条里有 6 条
    是这样，而且全是字母序上的邻居（invitation↔iron、moments↔money）。

    词典是按字母排的，漏掉的那个关键词一定落在「本组关键词」和「下一组关键词」
    之间。拿这个区间去条目文本里筛，基本能唯一确定：
    `have many/several irons in the fire` 挂在 invitation 下、下一组是 ironing，
    区间 (invitation, ironing) 里只有 `irons` 对得上。
    """
    heads = [(i, r[0]) for i, r in enumerate(rows) if r[0]]
    moved = 0
    for n, (start, word) in enumerate(heads):
        nxt = heads[n + 1][0] if n + 1 < len(heads) else len(rows)
        after = heads[n + 1][1].lower() if n + 1 < len(heads) else "zzzzz"
        lo = word.lower()
        stem = STEM.sub("", lo)
        pending = None
        for i in range(start, nxt):
            body = bare(rows[i][1])
            if stem and (stem in body or lo in body):
                pending = None
                continue
            # 边界错位一格：这一条其实属于下一组（`have ˌmoney to ˈburn` 排在
            # moments 组末尾，而下一组正是 money）。把它划过去就行
            nstem = STEM.sub("", after)
            if nstem and (nstem in body or after in body):
                rows[i][0] = after
                if nxt < len(rows):
                    rows[nxt][0] = ""
                moved += 1
                pending = after
                continue
            cands = {w for w in re.findall(r"[a-z]{3,}", body)
                     if lo < w < after and STEM.sub("", w) != stem}
            # 这里的虚词表要比 FUNC 窄——`all`、`that`、`there`、`one` 本身
            # 就是牛津的关键词，拿 FUNC 去减会把它们一起滤掉
            cands -= {"the", "and", "for", "with", "sth", "sbs", "sths",
                      "etc", "your", "yours", "his", "her", "their", "our",
                      "you", "she", "him", "them", "its", "was", "were",
                      "are", "has", "had", "not", "but", "than", "too"}
            if len(cands) != 1:
                continue
            new = cands.pop()
            if new != pending:                # 同一个新关键词只在第一条上标
                rows[i][0] = new
                pending = new
                moved += 1
    return rows, moved


def tidy_idiom(idiom):
    """条目文本的收尾：截断的变体、整条重复。

    原书用 `•` 分隔同义变体（`ˌnight and ˈday •ˌday and ˈnight`），这是正经体例，
    不能一律拆掉。但变体正好落在栏底时会被切断，留下半截
    （`every man has his ˈprice •everyone has`、`get/have/take the ˈmeasure of sb • get/`），
    这种半截没有信息量，删掉比留着强。判据：`•` 后那段以虚词/斜杠收尾，或不足两个词。
    """
    # 例句碎片粘在条目前面：`mechanic explained that they would have to ˈmake it`、
    # `sitting in a cafe minding my own business when a mind your ˌP's and ˈQ's`。
    # 判据要窄，否则会切掉 `when the cat's aˈway the mice will ˈplay` 这类正经谚语：
    # 前缀必须是**限定句**（`…ed that`、`which is`）或 -ing 分句，且后面还有重音符号
    # 原书的派生词块（`ˈwheel-spinning noun: Save yourself some…`）被整段抽了进来，
    # 冒号后面是例句正文，不是条目的一部分
    idiom = re.sub(r"\s*\b(noun|verb|adjective|adverb)\b\s*[:：].*$", "", idiom)
    # 条目在栏底被切断时末尾会留个孤零零的斜杠（`ˌsomething like ˈsb/`），去掉
    idiom = re.sub(r"\s*/\s*$", "", idiom)

    m = next((x for x in (p.match(idiom) for p in PROSE_HEAD) if x), None)
    if m and re.search(r"[ˈˌ]", idiom[m.end():]):
        rest = idiom[m.end():]
        # 从碎片之后的第一个带重音符号的词开始才是条目本体，再往前捡回
        # be / a / your 这类习语常见的起手词（`which is be sb's ˌspiritual ˈhome`）
        w = re.search(r"\S*[ˈˌ]\S*", rest)
        head = rest[:w.start()].split()
        while head and head[-1].lower() not in IDIOM_HEAD:
            head.pop()
        idiom = " ".join(head[-3:] + rest[w.start():].split())

    parts = [p.strip() for p in re.split(r"\s*[•◆]\s*", idiom) if p.strip()]
    keep = [parts[0]] if parts else []
    for p in parts[1:]:
        if len(p.split()) >= 2 and not p.endswith("/") and not DANGLING.search(p):
            keep.append(p)
    out = " • ".join(keep)
    # 同一条被抄了两遍（`a force to be ˈreckoned with a force to be ˈreckoned with`）
    half = len(out) // 2
    if len(out) > 12 and out[:half].strip() == out[half:].strip():
        out = out[:half].strip()
    return out.strip(' "\u201c\u201d') or idiom


def append_lost(rows):
    """把 09_lost.py 捞回来的条目插回它该在的关键词下面。

    这些是原书两条习语被 OCR 挤进同一行、抽取时只留下一条而整条丢掉的
    （`drive a hard ˈbargain what sb is ˈdriving at` 丢了前半）。
    子 agent 已经逐条核过、去掉了全书已有的，所以这里不再参与去重——
    `now, ˈnow` 和已有的 `now... now...` 去掉标点后长得一样，但它们是两条。
    """
    path = os.path.join(DATA, "lost.json")
    if not os.path.exists(path):
        return rows, 0
    lost = [v for v in json.load(open(path)).values() if v]
    # 关键词 → 该组最后一行的下标
    tail, word = {}, ""
    for i, r in enumerate(rows):
        word = r[0] or word
        tail[word.lower()] = i
    added = []
    for rec in lost:
        cands = [rec.get("w", "")] + re.findall(r"[A-Za-z]{3,}", bare(rec["i"]))
        for c in cands:
            if c.lower() in tail:
                en, _, cn_ex = rec["e"].partition("  ")
                added.append((tail[c.lower()],
                              ("", rec["i"], rec["cn"], en, cn_ex, True, True, "")))
                break
    for at, row in sorted(added, key=lambda x: -x[0]):
        rows.insert(at + 1, row)
    return rows, len(added)


def with_book_examples(rows):
    """例句优先用原书的，只有原书那条被 OCR 毁了才退回模型自拟的。

    原书例句是词典的权威内容。第一版成品全用了模型自拟的例句，是我沿用另一本书的
    做法、没单独确认——改回来：`data/examples.json` 里是清理过、判定可用的原书例句
    （5257 条抽出来，可用 4374 条），按条目序号回查。
    """
    path = os.path.join(DATA, "examples.json")
    if not os.path.exists(path):
        return rows, 0
    ex = json.load(open(path))
    used = 0
    for r in rows:
        got = ex.get(r[7]) if len(r) > 7 else None
        # 再验一次「例句真的用上了这条习语」。10_clean_ex 是按 idioms.json 的原始
        # 条目文本判的，而这里的条目已经过改挂、纠正关键词、拼回断行，对应关系会漂
        if got and not _p10.uses_idiom(got["en"], r[1]):
            got = None
        if got:
            r[3], r[4] = got["en"], got["cn"]
            used += 1
        elif r[3]:
            # 自拟例句没走过 10_clean_ex 的清理，字面收尾（标点后空格、句中被
            # 无故大写的词）得在这儿补上，否则两种来源的例句排版不一致
            r[3], r[4] = polish(r[3]), polish_cn(r[4])
            r[4] = (r[4] + "（自拟）").lstrip("（") if r[4] else ""
            r[4] = r[4] if r[4].endswith("（自拟）") else r[4] + "（自拟）"
    return rows, used


# 条目里可以对不上的虚词位。`be about to do sth` 在例句里是 `was about to phone`，
# be 变成了 was、do 变成了 phone，卡死这些位置会有两成例句加不上粗
# 中间还会插进宾语（`put his years in the kitchen to good account`），
# 所以允许连续跳过 6 个词——跳过的部分本来就属于「这条习语用起来的样子」，
# 一并加粗才对。所有格占位 sb's / sth's 例句里换成 his / her / your，也要能跳
SKIPPABLE = {"be", "is", "are", "was", "were", "been", "being", "get", "gets",
             "got", "to", "a", "an", "the", "it", "do", "does", "did", "done",
             "sb's", "sth's", "one's", "your", "his", "her", "their", "my"}


# 不规则动词。例句里是 took / brought / ran / got，跟条目里的原形对不上，
# 少了这张表有一成例句加不上粗
IRREG = {}
for _base, _forms in {
        "be": "am is are was were been", "have": "has had", "do": "does did done",
        "go": "goes went gone", "get": "gets got gotten", "take": "takes took taken",
        "make": "makes made", "come": "comes came", "give": "gives gave given",
        "run": "runs ran", "bring": "brings brought", "think": "thinks thought",
        "see": "sees saw seen", "say": "says said", "tell": "tells told",
        "know": "knows knew known", "put": "puts", "keep": "keeps kept",
        "leave": "leaves left", "find": "finds found", "feel": "feels felt",
        "hold": "holds held", "lose": "loses lost", "pay": "pays paid",
        "sell": "sells sold", "send": "sends sent", "set": "sets",
        "sit": "sits sat", "stand": "stands stood", "throw": "throws threw thrown",
        "win": "wins won", "write": "writes wrote written", "draw": "draws drew drawn",
        "drive": "drives drove driven", "eat": "eats ate eaten",
        "fall": "falls fell fallen", "fly": "flies flew flown",
        "break": "breaks broke broken", "catch": "catches caught",
        "buy": "buys bought", "blow": "blows blew blown", "beat": "beats",
        "cut": "cuts", "hit": "hits", "hurt": "hurts", "let": "lets",
        "read": "reads", "speak": "speaks spoke spoken", "spend": "spends spent",
        "wear": "wears wore worn", "cast": "casts", "shake": "shakes shook shaken",
        "strike": "strikes struck", "swear": "swears swore sworn",
        "tear": "tears tore torn", "meet": "meets met", "lead": "leads led",
        "lay": "lays laid", "lie": "lies lay lain", "rise": "rises rose risen",
        "ring": "rings rang rung", "sing": "sings sang sung",
        "sink": "sinks sank sunk", "stick": "sticks stuck", "shoot": "shoots shot",
        "steal": "steals stole stolen", "teach": "teaches taught",
        "understand": "understands understood", "wake": "wakes woke woken"}.items():
    for _f in (_base + " " + _forms).split():
        IRREG.setdefault(_f, set()).update((_base + " " + _forms).split())


def bold_idiom(en, idiom):
    """把例句里用到这条习语的那一段整体加粗。

    加粗必须是**连着的一段**，虚词也要包进去——`get sth off your ˈchest` 在例句里是
    `get it off my chest`，只挑实词会印成「**get** it off my **chest**」，读者看不出
    这是一个整体。

    做法是按**词序对齐**，不是「首尾实词之间全包」。后者会被零星撞词带偏：
    `that's about ˈall/it` 撞上 `Milk, bread, a bag of rice — that's about it`
    里的 a，就从句首一路粗到句中。对齐时允许跳词（例句里会多出 the/my/his）
    和屈折变化（`take ˈaim` → `taking aim`），但连续跳超过 2 个词就断开。
    """
    if not en or "<b>" in en:
        return en
    # 一格里可能并列着几个变体（`take sth into acˈcount • take account of sth`），
    # 得逐个试。把它们连在一起当成一条去对齐，哪条都对不上
    if "•" in idiom:
        for part in idiom.split("•"):
            out = bold_idiom(en, part.strip())
            if out != en:
                return out
        return en
    bare = re.sub(r"\([^)]*\)", " ", idiom).replace("ˈ", "").replace("ˌ", "")
    # 斜杠是可替换成分，`give/get` 命中任意一个都算
    groups = []
    for tok in re.findall(r"[A-Za-z][A-Za-z/'’-]*", bare.lower()):
        alts = [w for w in tok.split("/") if len(w) > 1 and w not in ("sth", "sb")]
        # 反身代词按人称变（`above yourself` → `above himself`），当一组处理；
        # do 是「做某事」的占位，例句里换成任何动词都算（`about to do sth` → `to phone`）
        if any(w.endswith(("self", "selves")) for w in alts):
            alts = ["yourself", "himself", "herself", "myself", "itself",
                    "themselves", "ourselves", "yourselves", "oneself"]
        if alts:
            groups.append(alts)
    if not groups:
        return en
    DO = {"do", "does", "did", "doing", "done"}
    groups = [g for g in groups if not (len(g) == 1 and g[0] in DO)]
    content = sum(1 for g in groups if any(w not in _p10.PLACEHOLDER for w in g))
    toks = list(re.finditer(r"[A-Za-z][A-Za-z'’-]*[A-Za-z]|[A-Za-z]", en))

    def same(word, alts):
        w = word.lower().strip("'’")
        return any(w == a or w in IRREG.get(a, ()) or a in IRREG.get(w, ())
                   or (len(a) > 3 and w.startswith(a[:len(a) - 2]))
                   or (len(w) > 3 and a.startswith(w[:len(w) - 2])) for a in alts)

    best = None
    for s0 in range(len(toks)):
        j = k = 0
        hits, first, last, gap, skips = 0, None, s0, 0, 0
        while j < len(groups) and s0 + k < len(toks):
            if same(toks[s0 + k].group(0), groups[j]):
                if first is None:
                    first = s0 + k          # 起点是**第一个命中**，不是扫描起点
                hits, last, j, k, gap = hits + 1, s0 + k, j + 1, k + 1, 0
            elif any(w in _p10.PLACEHOLDER or w in SKIPPABLE for w in groups[j]):
                j += 1                      # 例句里可以没有、或换掉这个虚词
            elif (j + 1 < len(groups) and skips == 0
                  and same(toks[s0 + k].group(0), groups[j + 1])):
                # 当前词对不上这一位、却正好对上下一位 → 这一位在例句里被换掉了
                # （`I/I'll ˈbet` 的例句是 `I bet…`，i'll 那一位没有对应）。
                # 必须**立刻**跳，等 gap 攒到 2 再跳的话指针早就越过 bet 了
                j, skips = j + 1, 1
            elif gap >= 2 and skips == 0:
                # 允许整个跳过一个实词位。条目里并列的动词只用得上一个
                # （`give yourself/ˌput on ˈairs` 的例句只有 put，没有 give）
                j, skips, gap = j + 1, 1, 0
            else:
                k, gap = k + 1, gap + 1
                if gap > 6:
                    break
        if hits and (best is None or hits > best[0]):
            best = (hits, first, last)
    # 实词至少对上六成。要求全对的话 `be about to do sth` 里的 do 对不上
    # 例句的 phone，7 成的例句都加不上粗。
    # 对不上六成也不能放着不加粗（规则 6：一条都不许跳）——例句常用同义替换
    # （`ˈvanishing act` 配的是 `disappearing act`），这时退而求其次，
    # 把命中的那几个实词连成一段粗体，至少让读者看出落点在哪
    if not best or best[0] < 1:
        return en
    a, b = toks[best[1]].start(), toks[best[2]].end()
    return en[:a] + "<b>" + en[a:b] + "</b>" + en[b:]


def letter_marks(rows):
    """每个首字母在哪一行开始分节 → {行号: 字母}。

    不能简单地「首字母一变就分节」：改挂关键词时会把 iron、money 这类补回原位，
    个别会打乱字母序，照单全收的话字母段来回跳（书签排出来是 A B N T U…）。
    改成给每个字母找**最长的一段连续块**，只在那一段的开头分节，
    零星错位的关键词就并进它所在的字母段里。
    """
    word, letters = "", []
    for r in rows:
        word = r[0] or word
        letters.append(word[:1].upper() if word[:1].isascii() else "")
    best, i = {}, 0
    while i < len(letters):
        j = i
        while j < len(letters) and letters[j] == letters[i]:
            j += 1
        if letters[i].isalpha() and j - i > best.get(letters[i], (0, 0))[1]:
            best[letters[i]] = (i, j - i)
        i = j
    return {pos: letter for letter, (pos, _) in best.items()}


def main():
    book, cache = load()
    rows, joined, dropped, made_up, fixed, cross, folded = final_rows(book, cache)
    rows = [list(r) for r in rows]
    rows, from_book = with_book_examples(rows)
    rows, moved = regroup(rows)
    rows, recovered = append_lost(rows)      # 捞回来的那些是元组，统一成 list
    rows = [list(r) for r in rows]
    for r in rows:
        r[1] = tidy_idiom(r[1])
    filled = sum(1 for r in rows if r[5])

    os.makedirs(OUT, exist_ok=True)
    scores = load_scores()
    junked = 0
    kept_rows = []
    for r in rows:
        sc = scores.get(re.sub(r"[^a-z]", "", r[1].lower()))
        if fragment(r[1], sc):
            junked += 1
            continue
        kept_rows.append(r)
    rows = kept_rows
    scored = 0
    lines = ["# 牛津习语词典\n",
             f"\n{len(rows)} 条习语。例句 {from_book} 条用原书原文，"
             f"其余原书那句被 OCR 毁了，退回自拟并标「（自拟）」。\n",
             "\n常用 / 口语：★ 一颗，☆ 半颗，五颗为满。"
             "常用 = 在当代英语里有多常见；口语 = 多大程度上属于口头表达。\n",
             "\n<table>",
             "<thead><tr><th>习语</th><th>中文解释</th><th>常用 / 口语</th>"
             "<th>例句</th></tr></thead>"]
    marks = letter_marks(rows)
    for n, (_word, idiom, cn, en_ex, cn_ex, *_) in enumerate(rows):
        # 关键词首字母的分节条：Markdown 里是个小标题条，
        # 排 PDF 时 13_pdf.py 靠它建 A-Z 书签（成品没有单词列，只能这么标）
        if n in marks:
            lines.append(f'<tr class="sec"><td colspan="4">{marks[n]}</td></tr>')
        sc = scores.get(re.sub(r"[^a-z]", "", idiom.lower()))
        if sc:
            scored += 1
            # 两行星级要标清楚哪行是哪个，光两排星分不出来
            rank = (f'<span class="lab">常</span>{stars(sc["u"])}<br>'
                    f'<span class="lab">口</span>{stars(sc["s"])}')
        else:
            # 没打到分的 18 条也不能留空格子——读者看到空白只会以为漏印了。
            # 给全书中位数（常 3 / 口 3）并不比空白更不准，至少版面是完整的
            rank = (f'<span class="lab">常</span>{stars(3)}<br>'
                    f'<span class="lab">口</span>{stars(3)}')
        ex = (f"{bold_idiom(cell(en_ex), idiom)}<br>{cell(cn_ex)}"
              if cn_ex else bold_idiom(cell(en_ex), idiom))
        lines.append(f"<tr><td><b>{glue_stress(shrink_tags(cell(strip_marker(idiom))))}</b></td>"
                     f"<td>{cell(cn)}</td><td>{rank}</td><td>{ex}</td></tr>")
    lines.append("</table>\n")
    p = os.path.join(OUT, "牛津习语词典.md")
    open(p, "w").write("\n".join(lines))
    print(f"{scored} 条习语（按打分又剔掉 {junked} 条残片）")
    print(f"  拼回断行条目 {joined} 条，去掉重复/音标残片 {dropped} 条，"
          f"剔除模型猜出来的 {made_up} 条，纠正关键词 {fixed} 个，"
          f"合并跨词条重复 {cross} 条，收拢断开的后半截 {folded} 条，"
          f"捞回被挤掉的 {recovered} 条，改挂错位条目 {moved} 条\n"
          f"  例句：原书 {from_book} 条，其余自拟")
    print(p)


# 判「例句用上习语没有」也要认 lose→lost、wine→wining，跟加粗共用一张表。
# 必须放在 main() 调用之前，否则跑脚本时 uses_idiom 拿到的还是空表
_p10.IRREG = IRREG

if __name__ == "__main__":
    main()