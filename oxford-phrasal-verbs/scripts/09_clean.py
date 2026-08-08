"""Pass 09: 成品清洗。渲染前每一行过一遍：**能修的修，修不了的整行不要**。

**从 `oxford-collocations/scripts/09_clean.py` 拷过来改的**，中文那套清洗
（汉字间空格按 jieba 分词判、半角标点转全角、解释列按义项逐条判）一模一样，
换掉的是列的判据：搭配换成短语动词（`bad_pv`），多了一列语法模式。

短语动词列跟搭配列的区别：
- **重音符号 ˈ ˌ 必须留着**，那是原书标出来的读音重点，也是条目的身份标记；
- 斜杠、分号是正经写法（`ˌbrick sth ˈin/up`、`ˌmuscle ˈup; ˌmuscle sth ˈup`）；
- 括号里是语域标签或可选成分，**括号必须配平**——扫描件常把右括号吃掉。

**宁可少印一行，也不能印错一行**：短语动词修不好整行丢掉；
释义和例句修不好就留空（但不许留空格子，见 `clean_row`）。

Usage: 09_clean.py        # 只统计，看会丢掉多少行
"""
import collections
import importlib.util
import json
import os
import re
import sys

import jieba
from wordfreq import zipf_frequency

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

_spec = importlib.util.spec_from_file_location("p04", os.path.join(HERE, "04_expand.py"))
p04 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p04)

CJK = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")
HAN = re.compile(r"[\u4e00-\u9fff]")           # 只认汉字，不含中文标点
# 搭配里允许出现的非英语词：占位符和词典标签（一律小写来比）
PLACE = {"sb", "sth", "sb's", "sth's", "one's", "sb’s", "sth’s",
         "etc", "esp", "ie", "eg", "usu",
         "bre", "ame", "name", "auste", "cane", "irishe", "scote", "safre",
         "informal", "formal", "figurative", "literary", "slang", "humorous",
         "disapproving", "approving", "technical", "spoken", "written",
         "especially", "usually", "sometimes", "both", "all", "old-fashioned"}
# 原书的组类型标记，串进搭配就是切分错位
MARKER = re.compile(
    r"(?:^|[\s/(])(ADJ|ADV|PREP|VERB|NOUN|PHRASES?|QUANT|PHR|IDM|NOTE"
    r"|ERB|OUN|DJ|REP)\b\.?", re.A)
# 正经的全大写词，别当成标记
CAPS_OK = {"BBC", "TV", "UK", "US", "USA", "EU", "UN", "AIDS", "HIV", "DNA",
           "CD", "DVD", "PC", "VAT", "ID", "MP", "GDP", "IT", "AD", "BC",
           "OK", "PE", "GP", "TB", "UV", "FBI", "CIA", "NHS", "EEC", "AGM",
           "IQ", "PIN", "VIP", "SUV", "GM", "PR", "TLC", "RSI", "ATM", "I"}
# 搭配格子里允许的字符：英文、数字、撇号、连字符、斜杠变体、括号标签
# `*` 从允许集里拿掉：搭配里没有任何合法用途，出现就是 OCR 把脚注、符号认了进来
# （`admissions are associated with alcohol.*70%`、`rate it * hospital admission`）
OK_CHARS = re.compile(r"^[A-Za-z0-9 '’/()\[\]\-,.&!?+~%$£€°=;:\"“”]*$")
# 英式拼写在 wordfreq 里普遍偏低，词表也收不全，别当成 OCR 错字
BRITISH = {"belabour", "labour", "favour", "honour", "colour", "flavour",
           "behaviour", "neighbour", "endeavour", "rumour", "humour",
           "practise", "organise", "recognise", "realise", "analyse",
           "centre", "theatre", "metre", "litre", "programme", "cheque",
           "grey", "tyre", "kerb", "plough", "storey", "aeroplane"}
# 句子才有的主谓结构，搭配里出现就是整句正文被抽进来了
SUBJ = re.compile(
    r"\b(this|that|there|it|he|she|they|we|you|i)\s+"
    r"(is|was|are|were|has|had|have|will|would|can|could|should|must|does|"
    r"did|do|says|said|seems|looks|makes|took|gets|got)\b", re.I)
# 搭配不会拿代词主语开头
LEAD_SUBJ = re.compile(r"^(this|that|these|those|there|it|he|she|they|we|you)\s", re.I)


# 上面那条规则会误伤的短词，都是全书里实际出现过的正经词条
SHORT_OK = {"writ", "loo", "omen", "tart", "rout", "nigh", "lass", "stag",
            "vie", "boa", "hem", "gent", "whit", "pus", "nit", "bran", "fro",
            "wag", "vet", "ebb", "awe", "vow", "wry", "apt", "eel", "oak"}


def odd_caps(w):
    """词中间冒出大写字母：`terracE`、`minuteS`、`accoladeS`。
    原书用的是小型大写字母，OCR 认成了大写，拼出来就是这德行。
    `BrE`/`AmE` 这些词典标签是正经的，放过。"""
    return bool(re.search(r"[a-z][A-Z]", w)) and w.lower() not in PLACE


def bad_word(w):
    """这个词是不是坏词。`fix_token` 已经修过一轮，还坏就是修不动的。"""
    from wordfreq import zipf_frequency as z
    low = w.lower().strip("'’")
    if low in PLACE or low in BRITISH or len(low) < 3:
        return False
    # 带前缀的派生词词表收不全，但**前缀后面得真是个词**才放过：
    # 光看开头两个字母，`realixed` 会因为以 re 开头被当成好词放过去
    m = re.match(r"(semi|nano|micro|multi|inter|over|under|non|anti|pre|post|re|un)"
                 r"-?(\w{4,})$", low)
    if m and p04.real_word(m.group(2)):
        return False
    if len(low) > 11 or re.search(
            r"(ingly|edly|ously|ily|ness|ment|ship|able|less)$", low):
        return False
    # 三四个字母的残词 web2 全都收（ast、ike、ost、ist、dea、fil、rea 都在里面），
    # 查词表和查词频一个都拦不住，印出来就是 `ast to arrive`、`dea affair`。
    # 判据：**补一个字母就能变成常见得多的词**，那它多半就是被吃掉了首字母
    # 门槛从 4 收到 3：`aced`（ace 的过去式）这类四字母词补一个字母就能变成
    # 常见得多的词，一卡就把 `The company aced out its rival` 整句丢掉
    if len(low) <= 3 and z(low, "en") < 3.5 and low not in SHORT_OK:
        base = z(low, "en")
        if any(max(z(c + low, "en"), z(low + c, "en")) > base + 1.5
               for c in "abcdefghijklmnopqrstuvwxyz"):
            return True
    return not p04.real_word(low) and z(low, "en") < 3.0


# 原书写在搭配后面的括号注解：`(= the right to live in a place)`。
# 那是释义，不该占搭配格；而且扫描件常把右括号吃掉，留个半拉括号在那儿
GLOSS = re.compile(r"\(=[^)]*\)?")
# 中文标点混进英文里：`～` `⋯` 是原书的省略号和词头占位符，去掉就好；
# `。，、《》` 这类是切分切错了地方，救不回来
CN_FILLER = re.compile(r"[～〜~⋯…·•◆◇＊]")
CN_PUNCT = re.compile(r"[。，、；：！？（）《》「」【】]")


# 形近误认：go→g0、to→t0、advances→advance5、almonds→almond5。
# 跟习语词典同一套办法——按形近逐个回代，只有回代出来的是真词才改
CONFUSE = {"0": "o", "1": ["l", "i", "t"], "2": ["z", "a"], "3": "e", "4": "a",
           "5": "s", "6": "b", "7": "t", "8": ["g", "b"], "9": "g"}


def respell(word):
    """把词里的形近数字还原成字母。本来就是真词的、纯数字的都不碰。"""
    if not re.search(r"[A-Za-z]", word) or not re.search(r"\d", word):
        return word
    # 短 token 不走「本来就是词」这条捷径：t0、a1 之类在语料里也有一定频率，
    # 放过去就修不掉了（`t0 the point` 其实是 `to the point`）
    if len(word) >= 4 and zipf_frequency(word.lower(), "en") >= 2.5:
        return word
    pos = [i for i, ch in enumerate(word) if ch in CONFUSE]
    if not pos or len(pos) > 3:
        return word
    cands = [list(word)]
    for i in pos:
        alts = CONFUSE[word[i]]
        alts = [alts] if isinstance(alts, str) else alts
        cands = [c[:i] + [a] + c[i + 1:] for c in cands for a in alts]
    for c in cands:
        w = "".join(c)
        if zipf_frequency(w.lower(), "en") >= 2.5:
            return w
    # 整体还原不出真词的，多半是两个词被数字粘住了：`claim0f` = claim of、
    # `aspect1o` = aspect to、`2007consensus` = 2007 consensus。
    # 在每个位置切一刀，两半都能还原成真词才认
    # 候选很多（1 可以还原成 l / i / t），挑两半词频之和最高的那个，
    # 不能取第一个撞上的——`aspect1o` 会先撞出 `aspect lo`，其实是 `aspect to`
    best, score = None, 0
    for c in cands:
        w = "".join(c)
        for i in range(2, len(w) - 1):
            a, b = w[:i], w[i:]
            za = zipf_frequency(a.lower(), "en")
            zb = zipf_frequency(b.lower(), "en")
            if za >= 3 and zb >= 3 and za + zb > score:
                best, score = a + " " + b, za + zb
    if best:
        return best
    for i in range(1, len(word)):
        a, b = word[:i], word[i:]
        if a.isdigit() and zipf_frequency(b.lower(), "en") >= 3:
            return a + " " + b
    # `colony5` = colonies、`hobby5` = hobbies：复数的 -ies 被压成了一个 5，
    # 逐字符替换救不回来，得整段换
    m = re.fullmatch(r"(\w+?)y5", word, re.I)
    if m and zipf_frequency(m.group(1).lower() + "ies", "en") >= 2.5:
        return m.group(1) + "ies"
    return word


def norm_phrase(p):
    """判好坏之前先把渣子扫掉，扫完是什么样就印什么样。"""
    p = GLOSS.sub(" ", (p or "").replace("’", "'"))
    p = CN_FILLER.sub(" ", p)
    p = re.sub(r"\.{2,}", " ", p)                     # `across.. terrain`
    if "(" in p and p.count("(") != p.count(")"):   # 括号没配对，从那儿截断
        p = p[:p.index("(")]
    p = p.replace(")", "") if "(" not in p else p
    p = re.sub(r"\s+-+\s*|\s*-+\s+", " ", p)          # `last- - try` 里的游离连字符
    p = re.sub(r"\s+", " ", p).strip(" ,.;:-—/|")
    # 断行拼接时同一个词接了两遍：`have to to admire`、`with with ability`、
    # `had a a passing acquaintance`。去掉重复的那个，搭配本身是好的
    p = re.sub(r"\b(\w+) \1\b", r"\1", p, flags=re.I)
    # `£15` 的镑号被认成 E，跟 admire 那批一样
    p = re.sub(r"\bE(?=\d)", "£", p)
    return re.sub(r"[A-Za-z]*\d[A-Za-z\d]*", lambda m: respell(m.group(0)), p)


# 词典里正经的缩写：它们后面的句点是自己的，不是句末标点
ABBR = {"esp", "etc", "usu", "ie", "eg", "approx", "incl", "vs", "sb", "sth",
        "mr", "mrs", "ms", "dr", "st", "no", "ext", "fig", "adj", "adv",
        "prep", "e", "i", "g", "oz", "lb", "ft"}
# 英语里正经的两字母词。除此之外的两字母 token 都是 OCR 碎渣（`abode aw`）
TWO_OK = set("of in on to at it is as an or by up no we do go so my he be us "
             "if me am id ok tv pm ha oh ah re ex ye ad".split())


def bad_phrase(p):
    """搭配格子里的一条。返回坏在哪儿，好的返回空串。"""
    p = p.strip()
    if not p:
        return "空"
    if CN_PUNCT.search(p) or CJK.search(p):
        return "混中文"
    if not OK_CHARS.match(p):
        return "怪符号"
    if MARKER.search(p) or any(
            t.isupper() and len(t) >= 2 and t not in CAPS_OK
            for t in re.findall(r"[A-Za-z]{2,}", p)):
        return "混标记"
    # `a 16-digit number`、`the 22nd amendment` 里的数字是正经的。
    # 但**字母和数字粘在同一个 token 里**一定是 OCR 认错（`hiccups5`、
    # `2007consensus`）——respell 已经尽力还原过一轮，还留着就说明救不回来
    for t in p.split():
        if re.search(r"\d", t) and re.search(r"[A-Za-z]", t) and not re.fullmatch(
                r"\d+(-\w+|st|nd|rd|th|s)|[A-Z]{2,}\d", t):
            return "夹数字"
    # 书里的逗号被扫成了句点，`growing, increasing` 成了 `growing. increasing`，
    # 两条搭配黏成一条；也有半句正文被切进来的（`asbestos. Carbon lib`、
    # `modules. 1 complete`、`acted cool toward you. (AmE)`）。切不回去，整行丢掉。
    # **句点后面不管跟的是大写、小写还是数字，一律算坏**——只卡小写的话
    # 那三种全漏；但要放过词典缩写（`(esp. BrE)`、`etc.`），不然误伤一大片
    for m in re.finditer(r"([A-Za-z]+)\.(?=\s)", p):
        if m.group(1).lower() not in ABBR:
            return "两条黏一起"
    # 游离的句点、逗号（`replacements' .subs'`、`manufacture .BrE steel`）
    if re.search(r"(?:^|\s)[.,]", p):
        return "游离标点"
    words = p.split()
    if len(words) > 9 or (re.search(r"[?!]", p) and len(words) > 5):
        return "其实是句子"
    # **搭配至少两个词**。孤零零一个词说明代替词头的 `~` 在 OCR 里丢了：
    # `age`（其实是 school age）、`ale`（demand for real ale）、`provide`
    # （provide accommodation）。补不回正确语序，整条不要。
    # 带连字符/斜杠的单 token 是正经的（`hit-and-run`、`fibre-optic/fiber-optic`）
    if len(words) == 1 and not re.search(r"[-/]", p):
        return "只有一个词"
    # 例句碎片被当成了搭配。搭配里不会出现人称代词的缩写
    # （`Once you've had some sleep you able`），出现就是整句被切了进来
    if re.search(r"\b(you|I|he|she|we|they|it|there|that)'(ve|re|ll|d|s|m)\b", p, re.I):
        return "其实是句子"
    # 断行留下的半截：`take up your`、`affection year for the`、`or humorous abode`。
    # 只挡限定词和连词——介词收尾是正经的（`abbreviation for`、`abandon in favour of`）
    if re.fullmatch(r"(the|a|an|your|my|his|her|their|its|our|and|or|but|that|this)",
                    words[-1], re.I):
        return "半截 尾巴是限定词"
    if re.fullmatch(r"(and|or|but)", words[0], re.I):
        return "半截 开头是连词"
    # `abode aw`、`abode ive`：两个字母的碎渣，只放行真的两字母词
    if any(len(w) == 2 and w.lower() not in TWO_OK
           for w in re.findall(r"[A-Za-z]+", p)):
        return "两字母碎渣"
    if SUBJ.search(p) or LEAD_SUBJ.match(p):
        return "其实是句子"
    # 首字母被吃掉，剩个孤零零的字母：`n accepting`、`t wil`、`s this`。
    # a 和 I 是正经的（`a matter of time`、`I bet`）
    if re.search(r"(?:^|\s)[b-hj-z](?:\s|$)", p, re.I):
        return "缺首字母"
    for w in re.findall(r"[A-Za-z][A-Za-z'’]*", p):
        if odd_caps(w):
            return f"词中大写 {w}"
        if bad_word(w):
            return f"坏词 {w}"
    return ""


def bad_head(word):
    """词头坏没坏。查不到的词条一点用没有，整条不要——
    `thanktul adj` 这种词头，读者按 thankful 翻永远翻不到。"""
    return (not word or not re.fullmatch(r"[A-Za-z][A-Za-z' \-]*", word)
            or bad_word(word))


# ---- 解释列的义项级清洗（gloss=True 才走）----
# 解释列是「一串短义项」，不是句子。判「这一条是不是句子混进来了」：
# 人称/指示代词、句末语气词，或者长得离谱。**长度不能卡太紧**——
# `白人儿童与少数族裔儿童学习成绩的差异`（17 字）是正经义项
SENT_ITEM = re.compile(r"[我你他她它咱您这那]|[了吗呢吧]$")
# 义项之间的分隔符。原书用竖线，OCR 认成了 `；。，、！：？` 各种样子——
# 不能只认分号：`狠狠的！使劲的` 里的感叹号就是竖线，`！` 原样印出来像在喊
GLOSS_SEP = re.compile(r"[；;。，、！!：:？?]")
# 代替词头的省略号被认成汉字「一」：`向一踢`（应是 `向…踢`）、`对一有害`。
# 只在**介词后面**、而且**这条解释里还没有省略号**时才换——`在一起`、`一大笔`
# 里的「一」是正经的，`在⋯上的一吻` 的「一吻」也是
LONE_YI = re.compile(r"(?<=[向对给为从把跟与由受])一(?=[\u4e00-\u9fff])")


def drop_orphan_paren(t):
    """去掉没配对的括号。扫描件常把一半括号吃掉，剩下
    `对⋯踢；违抗⋯(`、`为人)打胎` 这种半拉括号。整段截掉太狠——
    后面往往还有好几条正经义项，只把那个孤立的括号抹掉。"""
    out, stack = [], []
    for ch in t:
        if ch in "（(":
            stack.append(len(out))
            out.append(ch)
        elif ch in "）)":
            if stack:
                stack.pop()
                out.append(ch)
        else:
            out.append(ch)
    for i in reversed(stack):
        out[i] = ""
    return "".join(out)


# 义项号和圆圈数字：`1 备份文件`、`①捣蛋`。中文释义里出现纯属抽取没切干净
GLOSS_NO = re.compile(r"(?:^|(?<=[；;。]))\s*[0-9①-⑳ⅠⅡⅢⅣⅤ]+\s*[.、)）]?\s*")


def clean_gloss(t):
    """解释列专用：切成义项，逐条判，句子混进来的整条扔掉。

    OCR 常把例句译文和下一个小类的义项一起卷进解释格，成品里就是
    `狠狠的！使劲的；用力的；…；凶猛的一踢 。(这个城市需要好好鞭策一下。空手道脚法`
    这种一路吃到隔壁的怪东西。逐条判比整段截断稳——
    `习得力。培养；增强；提高能力` 从句号处截会白丢三条正经义项。
    """
    t = drop_orphan_paren(t.replace("⋯", "…"))
    t = GLOSS_NO.sub("", t)
    # 释义里的 `•` 一律是省略号被认花了（`对••发号施令`、`与•致`），
    # 不是人名间隔号——间隔号只在例句译文里出现（`斯嘉丽•约翰逊`）
    t = re.sub(r"[•◇○〇◎◆●]+", "…", t)
    t = re.sub(r"…{2,}", "…", t)
    # 方括号、下划线、竖线这些是 OCR 把版面符号认了进来（`评论界的赞扬 ］`、
    # `道义责任 _`）。省略号前后的空格和后面拖的句点也一起抹掉（`…. 缺席期间`）
    t = re.sub(r"\s*…[\s.．]*", "…", t)
    keep, seen = [], set()
    for x in GLOSS_SEP.split(t):
        # **括号要切完再判**。整段的括号是配对的，切成义项之后两半分家，
        # `(；酪等)` 切出来就是一个光括号和 `酪等)`——整段判过一遍不算数
        x = drop_orphan_paren(x.strip(" ·-—"))
        # 义项里不该有空格：中文之间的空格 `fix_cn_spaces` 已经按分词判过了，
        # 到这儿还剩的都是紧贴省略号、括号的 OCR 空格（`在… 方面表现积极`）
        x = x.replace(" ", "")
        # 一个字的义项（`的`、`事`、`动`）是碎渣；重复的义项只留一条。
        # 只剩省略号、括号的也算碎渣
        if (len(x) < 2 or len(x) > 15 or SENT_ITEM.search(x) or x in seen
                or not HAN.search(x)):
            continue
        # 「一」该是省略号。**逐条判，不能看整格**——同一格里别处有个省略号，
        # 这条里的「一」照样是错的（`为一的做法`）；反过来看整格还会让结果
        # 跟上下文有关，同一条解释清两遍出两个样，自查永远收敛不了
        if LONE_YI.search(x):
            if "…" in x:
                pass                       # 已有省略号，剩下的「一」多半是正经的
            elif any(k == "一" for k in jieba.cut(x)):
                x = LONE_YI.sub("…", x)    # `向一踢` → `向…踢`
            else:
                continue    # `为一所爱`、`把一捆成包`：jieba 把它并进了 `一所`、
                            # `一捆` 这类量词短语，硬换会毁掉 `融为一体`。扔掉这条
        seen.add(x)
        keep.append(x)
    return "；".join(keep).strip(" ；·-—")


def clean_cn(cn, gloss=True):
    """解释列。OCR 常把隔壁栏的英文搭配和例句卷进来：

        电蓄热器 1 battery (AmE) 蓄电池
        薪金上调;工资的上涨 1 budget, dividend, fare, pr

    中文解释里本来就不该有成串的英文，所以**从第一处英文起整段截掉**，
    留下前面那截干净的中文。截完只剩标点就当空。

    `gloss=False` 是给例句译文用的：那是一句连贯的话，句号、逗号、
    感叹号都是正经标点，不能按义项切。
    """
    cn = re.sub(r"\s+", " ", (cn or "").strip())
    m = re.search(r"[A-Za-z]{2,}", cn)
    if m:
        cn = cn[:m.start()]
    # 方括号、下划线、竖线是 OCR 把版面符号认了进来。**两种模式都要清**——
    # 只在 gloss 分支里清的话，例句译文里的 `［E］` 会被后面的规则变成 `；`，
    # 印出来是 `…有违我的原则。；。`
    # `%` 和 `$£€` 不能删——例句译文里 `28%`、`500英镑` 是正经内容
    cn = re.sub(r"[~～*#^&<>\\/\[\]{}］［【】「」〔〕〈〉_]", " ", cn)
    # 书里用竖线分隔两条解释，扫成了 `1` `I` `l`；剩下的孤立字母数字也是碎渣。
    # 位置不限——`施虐者1受虐者`、`培养增强提高能力1` 都要清掉，
    # 卡「前后不是汉字」的话紧贴汉字的这些一个也清不掉
    if gloss:
        # 书里用竖线分隔两条义项，扫成了 `1` `I` `l`；剩下的孤立字母数字也是碎渣。
        # **这条只能用在释义列**——例句译文里的数字是正经内容
        # （`占所有举报罪案的28%`、`超过了500英镑`），一律换成分号就把
        # 数字全吃掉了，印出来是「占所有举报罪案的。」
        cn = re.sub(r"[0-9A-Za-z|｜]+", "；", cn)
        cn = re.sub(r"[；;]\s*(?=[；;])", "", cn)
    else:
        cn = re.sub(r"[|｜]+", "", cn)
    cn = re.sub(r"\s+", " ", cn).strip(" ,.;:、，。；：·-—")
    cn = fix_cn_spaces(halfwidth_to_full(cn))
    if gloss:
        cn = clean_gloss(cn)
    return cn if CJK.search(cn) else ""


def fix_cn_spaces(cn):
    """汉字之间的空格：词被 OCR 拆开了就合上，义项之间的换成分号。

    这两种长得一模一样，只能靠分词判——
    - `明确表 示钦佩` 合起来切成「明确/表示/钦佩」，空格正卡在「表示」中间 → 合上
    - `富有创意的 想象丰富的` 合起来切成「…的/想象/…」，空格落在词边界 → 义项分隔

    全书 38.6% 的解释格带这种空格。一律删会把并排的几条义项糊成一坨，
    一律留就是满页断词，只能分开处理。
    """
    def decide(m):
        left, right = m.group(1), m.group(2)
        joined, pos, cut = left + right, 0, len(left)
        for tok in jieba.cut(joined):
            if pos < cut < pos + len(tok):        # 切点落在某个词内部
                return joined
            pos += len(tok)
        return left + "；" + right

    prev = None
    while prev != cn:                             # 一格里可能有好几个空格，逐个判
        prev = cn
        cn = re.sub(r"([\u4e00-\u9fff]+) ([\u4e00-\u9fff]+)", decide, cn, count=1)
    return re.sub(r"；{2,}", "；", cn)


def halfwidth_to_full(t):
    """夹在汉字里的半角标点换成全角，不然字距明显不对。"""
    # 句号要先处理：它两边常带空格（`勉强承认 . 她不承认`），
    # 不先换掉的话后面按空格切义项会把一句话劈成两段
    t = re.sub(r"(?<=[\u4e00-\u9fff])\s*[.．]\s*(?=[\u4e00-\u9fff])", "。", t)
    for half, full in ((",", "，"), (";", "；"), (":", "："), ("?", "？"),
                       ("!", "！")):
        t = re.sub(rf"(?<=[\u4e00-\u9fff])\s*{re.escape(half)}", full, t)
    t = re.sub(r"\s*([，；：？！])\s*", r"\1", t)
    # `形成脓肿；长脓包。；. 我脖子上长了个脓包`：句号、分号、残留半角点挤在一起
    t = re.sub(r"[。．.]+\s*[；;]\s*[.．。]*", "。", t)
    t = re.sub(r"([，。；：！？])[，。；：！？\s.]+", r"\1", t)
    # 半角括号跟汉字之间会多出空格（`长时间不在(某处) 时间`）
    t = re.sub(r"\s*([()（）])\s*", r"\1", t)
    return t.strip("，；：·。")


# 不规则动词。例句里全是 `sent` `took` `made`，词形跟搭配里的原形对不上，
# 加粗就一大片标不出来（`send ambassador` → `The King sent an ambassador`）
IRREG = {
    "be": "am|is|are|was|were|been|being", "have": "has|had|having",
    "do": "does|did|done|doing", "go": "goes|went|gone|going",
    "take": "takes|took|taken|taking", "make": "makes|made|making",
    "get": "gets|got|gotten|getting", "give": "gives|gave|given|giving",
    "come": "comes|came|coming", "see": "sees|saw|seen|seeing",
    "say": "says|said|saying", "know": "knows|knew|known|knowing",
    "think": "thinks|thought|thinking", "find": "finds|found|finding",
    "tell": "tells|told|telling", "become": "becomes|became|becoming",
    "leave": "leaves|left|leaving", "feel": "feels|felt|feeling",
    "bring": "brings|brought|bringing", "begin": "begins|began|begun",
    "keep": "keeps|kept|keeping", "hold": "holds|held|holding",
    "write": "writes|wrote|written|writing", "stand": "stands|stood|standing",
    "hear": "hears|heard|hearing", "mean": "means|meant|meaning",
    "meet": "meets|met|meeting", "run": "runs|ran|running",
    "pay": "pays|paid|paying", "sit": "sits|sat|sitting",
    "speak": "speaks|spoke|spoken|speaking", "lead": "leads|led|leading",
    "grow": "grows|grew|grown|growing", "lose": "loses|lost|losing",
    "fall": "falls|fell|fallen|falling", "send": "sends|sent|sending",
    "build": "builds|built|building", "draw": "draws|drew|drawn|drawing",
    "break": "breaks|broke|broken|breaking", "spend": "spends|spent|spending",
    "rise": "rises|rose|risen|rising", "drive": "drives|drove|driven|driving",
    "buy": "buys|bought|buying", "wear": "wears|wore|worn|wearing",
    "choose": "chooses|chose|chosen|choosing", "seek": "seeks|sought|seeking",
    "throw": "throws|threw|thrown|throwing", "catch": "catches|caught|catching",
    "deal": "deals|dealt|dealing", "win": "wins|won|winning",
    "forget": "forgets|forgot|forgotten|forgetting", "lay": "lays|laid|laying",
    "sell": "sells|sold|selling", "fight": "fights|fought|fighting",
    "bear": "bears|bore|borne|bearing", "teach": "teaches|taught|teaching",
    "hang": "hangs|hung|hanging", "strike": "strikes|struck|striking",
    "shoot": "shoots|shot|shooting", "sing": "sings|sang|sung|singing",
    "hide": "hides|hid|hidden|hiding", "wake": "wakes|woke|woken|waking",
    "stick": "sticks|stuck|sticking", "bend": "bends|bent|bending",
    "blow": "blows|blew|blown|blowing", "ride": "rides|rode|ridden|riding",
    "steal": "steals|stole|stolen|stealing", "tear": "tears|tore|torn|tearing",
    "shake": "shakes|shook|shaken|shaking", "sink": "sinks|sank|sunk|sinking",
    "freeze": "freezes|froze|frozen|freezing", "arise": "arises|arose|arisen",
    "understand": "understands|understood|understanding",
    "bind": "binds|bound|binding", "feed": "feeds|fed|feeding",
    "lend": "lends|lent|lending", "shine": "shines|shone|shining",
    "flee": "flees|fled|fleeing", "cling": "clings|clung|clinging",
    "swing": "swings|swung|swinging", "spin": "spins|spun|spinning",
    "dig": "digs|dug|digging", "light": "lights|lit|lighting",
    "withdraw": "withdraws|withdrew|withdrawn|withdrawing",
    "overcome": "overcomes|overcame|overcoming",
    "uphold": "upholds|upheld|upholding",
}


def inflect(w):
    """一个词的正则，允许屈折变化。**结尾的 e/y 要单独处理**，
    不然 `ache` 匹配不上 `aching`、`carry` 匹配不上 `carried`，加粗漏一大片。
    直接在词尾接 `\\w{0,4}` 又太松，`care` 会把光秃秃的 `car` 也标黑。"""
    w = w.strip("()'’")
    esc = re.escape(w)
    if w.lower() in IRREG:
        return f"(?:{esc}|{IRREG[w.lower()]})"
    if len(w) > 4 and w.endswith("y"):
        return esc[:-1] + r"(?:y|ies|ied|ier|iest|ily|iness)"
    if len(w) > 3 and w.endswith("e"):
        return esc[:-1] + r"(?:e\w{0,3}|ing|ed|es|ation)"
    return esc + r"\w{0,4}"


# 判「例句对不对得上」时跳过的虚词：它们哪句话里都有，对上了也说明不了什么
FUNCTION = {"a", "an", "the", "of", "to", "in", "on", "at", "for", "with",
            "and", "or", "be", "is", "are", "was", "were", "your", "his",
            "her", "their", "its", "not", "but", "as", "by", "from", "that"}


def content_words(phrase):
    """搭配里真正有信息量的词。括号、斜杠、占位符都得先扒掉——
    `deliver a service (to sb)` 里的 `(to` 不扒掉就成了一个查不到的「实词」。"""
    out = []
    for w in re.split(r"[\s/]+", phrase or ""):
        w = w.strip("()[]'’,.;:!?").lower()
        if len(w) > 2 and w not in PLACE and w not in FUNCTION:
            out.append(w)
    return out


def hits(word, text):
    """例句里有没有这个词（允许屈折）。判「例句是不是在讲这条搭配」
    和判「加粗漏没漏」用的是同一个口径，不然两边永远对不上。"""
    return re.search(r"\b" + inflect(word) + r"\b", text or "", re.I) is not None


# 正经的两字母词。剩下的两字母「词」都是 OCR 渣：`Lo throw a big party` 的 Lo 是 to
TWO_OK = {"a", "i", "am", "an", "as", "at", "be", "by", "do", "go", "he", "hi",
          "if", "in", "is", "it", "me", "my", "no", "of", "oh", "ok", "on",
          "or", "so", "to", "up", "us", "we", "ah", "eh", "id", "ex", "tv",
          "pm", "ye", "ox", "re"}


def bad_sentence(plain, words=()):
    """例句坏在哪儿，好的返回空串。**清洗和自查用的是同一个函数**。"""
    # 短语动词的例句本来就可以很短（`He backed up.`），卡 5 个词会误杀一大批
    if not plain[:1].isupper() or len(plain.split()) < 4:
        return "不完整"
    if not plain.rstrip().endswith((".", "!", "?", "'", '"', "’", "”")):
        return "不完整"
    if CJK.search(plain):
        return "混中文"
    if MARKER.search(plain) or not OK_CHARS.match(plain):
        return "混标记"
    # 交叉引用被卷进来了：`Special page at BUSINESS arrangement with a`
    if any(t.isupper() and len(t) >= 3 and t not in CAPS_OK
           for t in re.findall(r"[A-Za-z]{2,}", plain)):
        return "混标记"
    # 例句里也会掉首字母：`We provide assistance i your car breaks down.`（i 是 if）
    if re.search(r"(?:^|\s)[b-hj-z](?:\s|$)", plain, re.I):
        return "缺首字母"
    # 缩写的 t 被吃掉：`We don' have the finances`
    if re.search(r"\b\w+n'(?![\w])", plain):
        return "缩写残缺"
    # 书里的 `~ed` 扫成了 `-d`，孤零零一个连字符开头的词
    if re.search(r"(?:^|\s)-", plain):
        return "残缺词"
    for w in re.findall(r"[A-Za-z][A-Za-z'’]*", plain):
        if odd_caps(w):
            return f"词中大写 {w}"
        if len(w) == 2 and w.lower() not in TWO_OK:
            return f"坏词 {w}"
        if bad_word(w):
            return f"坏词 {w}"
    # 例句得真的在讲这条搭配。一个词都对不上就是归错了小类
    if words and not any(hits(w, plain) for w in words):
        return "跟搭配对不上"
    return ""


def clean_ex(full, en, zh):
    """例句列。修不好就整条不要——宁可这行没例句，也不能印半句。"""
    en = re.sub(r"\s+", " ", (en or "").replace("’", "'").strip())
    # 例句也要过形近数字还原。以前只清搭配列，例句里的 `t0 any school`、
    # `made advance5 to`、`E15` 全都原样印出去了
    en = re.sub(r"\bE(?=\d)", "£", en)
    en = re.sub(r"[A-Za-z]*\d[A-Za-z\d]*", lambda m: respell(m.group(0)), en)
    zh = re.sub(r"\s+", " ", (zh or "").strip())
    plain = re.sub(r"</?b>", "", en)
    if not plain or bad_sentence(plain, content_words(full[0])):
        return "", ""
    # 例句里还留着字母数字混搭的（`hiccups5`），说明 respell 没救回来，整条不要
    if any(re.search(r"\d", t) and re.search(r"[A-Za-z]", t)
           and not re.fullmatch(r"\d+(-\w+|st|nd|rd|th|s)|[A-Z]{2,}\d", t)
           for t in plain.split()):
        return "", ""
    zh = clean_cn(zh, gloss=False)
    # 例句译文跟解释列不一样：它是一句连贯的话，汉字之间**不该有任何空格**，
    # `她暗地里对他又羡 又妒` 里那个空格纯粹是 OCR 的，别按义项分隔处理
    zh = re.sub(r"(?<=[\u4e00-\u9fff])[；\s]+(?=[\u4e00-\u9fff])", "", zh)
    # 句末拖着的半拉括号和重复标点：`加入公司养老金计划。(。`（176 处）。
    # 扫描件把下一句的开头刮进来了，抹掉就好
    zh = drop_orphan_paren(zh)
    # **收尾别把括号也剥掉**：`在五号交叉路口驶离(高速公路)` 的右括号被剥掉之后
    # 左括号就成了孤儿，而 drop_orphan_paren 已经跑过了，补不回来
    # 句末拖的残渣要**反复剥到不动为止**：`。；。`、`。•；'。` 是分号、
    # 例句引导符、撇号混在一起，一遍正则只剥得掉一层
    prev = None
    while prev != zh:
        prev = zh
        # 句末拖着的是**引导符 + 义项号**（`…五分钟。• 2。`、`…过目一下吗？•1。`）：
        # 下一条的开头被刮进来了。数字也要一起剥，只剥符号会留下个孤零零的 2
        # 引导符后面刮进来的可能是义项号、也可能是下一句的头几个字母数字
        # （`• a。`、`• 35 000。`、`•r'm。`），一并剥掉
        zh = re.sub(r"[•◇○〇◎◆●∘º][\sA-Za-z0-9'’]*[。．.]?\s*$", "", zh)
        # 引导符 ◇ 也常被认成一个孤零零的 0 / o / O。**只在句末标点或省略号
        # 后面才敢剥**——译文里的数字是正经内容，不能见数字就删
        zh = re.sub(r"(?<=[。！？…])\s*[0oO]\s*[。．.]?\s*$", "", zh)
        zh = re.sub(r"[。！？](?:[\s。．.！？；;，,、·•◇○〇◎◆●∘º]|$)+$", "。", zh)
        zh = zh.strip(" ，,、；;·•◇○〇◎◆●∘º-—'’\"")
    zh = re.sub(r"[◇○〇◎◆●∘º*|｜［］【】_]+", "", zh)
    zh = drop_orphan_paren(zh)
    if zh and not zh.endswith(("。", "！", "？", "”", "）")):
        zh += "。"
    return en, zh







# ---- 这本书专用：短语动词列、语法模式列、整行 ----
# 短语动词里允许的字符。**重音符号一定要留**，`;` `/` `()` 也是原书正经写法
PV_CHARS = re.compile(r"^[A-Za-zˈˌ0-9 '’/();,.\-+&!?]*$")
# 原书的语法模式记号，只有这几种词
PAT_OK = re.compile(r"^(?:v|n|pron|adv|prep|adj|sth|sb|be|get|"
                    r"rare|less|frequent|not|usually|especially|"
                    r"BrE|AmE|passive|in|the|used)$", re.I)


# 短语动词里正经的两字母词：小品词 + 虚词 + 占位符
PV_TWO_OK = set("of in on to at up it by be go do so no us we me my he if or "
                "as an sb ok tv am is".split())


def close(a, b):
    """两个词是不是同一个词的两种拼法：改一个字母、增删一个字母、
    或者相邻两个字母调个位（`bale`/`bail`、`fibre`/`fiber`）。"""
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    if len(a) == len(b):
        d = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        return len(d) <= 1 or (len(d) == 2 and d[1] == d[0] + 1
                               and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]])
    if abs(len(a) - len(b)) == 1:
        s, u = (a, b) if len(a) < len(b) else (b, a)
        return any(s == u[:i] + u[i + 1:] for i in range(len(u)))
    return False


def plain_pv(pv):
    """去掉重音符号的短语动词，用来判词和跟例句比对。"""
    return (pv or "").replace("ˈ", "").replace("ˌ", "")


def bad_pv(pv):
    """短语动词格子坏在哪儿，好的返回空串。"""
    pv = (pv or "").strip()
    if not pv:
        return "空"
    if CJK.search(pv):
        return "混中文"
    if not PV_CHARS.match(pv):
        return "怪符号"
    if "ˈ" not in pv and "ˌ" not in pv:
        return "没有重音符号"          # 原书每条都标重音，没有就是切歪了
    # 整条都在括号里的（`(AmE also ˌput sth aˈway)`）是上一条的变体说明，
    # 被悬挂缩进判据当成了新条目，它自己不是一个词条
    if pv.startswith(("(", "（")):
        return "整条在括号里"
    if pv != drop_orphan_paren(pv):
        return "括号不配对"
    # **判词之前先剥重音符号**：`aˈgree to sth` 被切成 `a` + `gree`，
    # `gree` 当成坏词，整条 agree 就印不出来了
    words = re.findall(r"[A-Za-z][A-Za-z'’]*", plain_pv(pv))
    if len(words) < 2:
        return "只有一个词"           # 短语动词至少是「动词 + 小品词」
    if len(pv) > 90 or len(words) > 14:
        return "太长"                 # 释义被算进条目里了
    # 模式行串进条目了：`flush sb/sth ˈout of adv + prep sth`。
    # 模式记号（`v + adv`、`n/pron`、`adv + prep`）只出现在模式行里，
    # 落到条目格就是 OCR 把两行并成了一行
    if re.search(r"\bn/pron\b|\b(?:v|n|adv|prep|pron|adj)\s*\+\s*(?:v|n|adv|prep|pron|adj)\b", pv):
        return "混进模式记号"
    # 释义的头被切进来了：`to`+动词、`used`、`if` 打头的从句
    if re.search(r"\b(?:used (?:to|when|for)|if (?:sb|sth|you|a|the)\b)", pv):
        return "混进释义"
    # **条目里不该有义项号**。`pull sb ˈup 1 (on/for sth) (BrE, informal) to bull
    # sb ˈup` 就是义项号后面整段释义都被算进条目了——义项号是释义的起点，
    # 它出现在条目里，说明 `cut_head` 切晚了
    # 数字一个都不许留。`give sb ˈup1`（义项号粘在小品词上）、`BrE1`、
    # `ˈup 1to become, or`（义项号后面整段释义被算进条目）——
    # 卡「前后是空格的孤立数字」的话，粘着字母的那些一个也查不出来
    if re.search(r"\d", pv):
        return "夹数字"
    for w in words:
        # 短语动词里的两字母词就那么几个（小品词和虚词），别的都是 OCR 碎渣
        if len(w) == 2 and w.lower() not in PV_TWO_OK:
            return f"两字母碎渣 {w}"
        if odd_caps(w):
            return f"词中大写 {w}"
        if bad_word(w):
            return f"坏词 {w}"
    return ""


def clean_pv(pv):
    """短语动词的字面收尾。`(formal)` 的左括号常被认成 C/l/i，右括号常被吃掉。"""
    pv = re.sub(r"\s+", " ", (pv or "").replace("’", "'")).strip()
    # `aˈbide by sth Cormal)` —— 左括号被认成了 C。只在「后面紧跟已知标签词 +
    # 右括号」时才敢改，不然会把正经的大写词吃掉
    pv = re.sub(r"\s[CIl(]?(ormal|nformal|rmal)\)", " (formal)", pv)
    pv = re.sub(r"\s*[,;]\s*$", "", pv)
    # 变体之间的分号被认成句点，还粘在一起：`shin ˈdown/ˈup.shin ˈdown/ˈup sth`。
    # 短语动词里不会有词中句点，两边都是字母的句点一律当分号
    pv = re.sub(r"(?<=[a-zA-Z])\.(?=[a-zˈˌ])", "; ", pv)
    # `sh` 是占位符 `sb` 被认错（33 处，`ˌwrite sh/sth ˈout of sth`）。
    # 只在它单独成词、且旁边就是 `sth` 或短语动词语境时才改
    pv = re.sub(r"\bsh\b(?=/sth|\s|$)", "sb", pv)
    # 行首多认出来的孤字母和圆点：`k aˈgree with sb`、`.blast sth ˈout`。
    # 扫描件左边缘常刮进上一行的笔画。`a`/`I` 是正经词，不能动
    pv = re.sub(r"^[.·•]+\s*", "", pv)
    # 行首多认出来的孤字母，两种形态：`k aˈgree with sb`、`f.put sth ˈback`。
    # 后一种没有空格，只卡带空格的那条漏一大半
    pv = re.sub(r"^([b-hj-z])[.\s]\s*(?=[a-zˈˌ])", "", pv)
    # 形近数字：`z0om ˈoff`、`,g0 ˈround`、`burn sth aˈway t0 disappear`
    pv = re.sub(r"[A-Za-z]*\d[A-Za-z\d]*", lambda m: respell(m.group(0)), pv)
    return drop_orphan_paren(pv).strip(" ,;:-")


def clean_tags(tags):
    """语域标签。只留短短的英文标签——`strip_tags` 在右括号被吃掉时会多吃几个词，
    吃出 `especially BrE；especially of a vehicle 尤指车辆` 这种夹中文的长尾巴。"""
    out = []
    for x in tags or []:
        x = re.sub(r"[；;]", ", ", re.sub(r"\s+", " ", x)).strip(" ,;.")
        if not x or CJK.search(x) or len(x) > 34 or not re.match(r"^[A-Za-z]", x):
            continue
        if x not in out:
            out.append(x)
    return out


def bad_tag(tags):
    """标签坏在哪儿。"""
    for x in tags or []:
        if CJK.search(x):
            return f"混中文 {x[:16]}"
        if len(x) > 34 or re.search(r"[；;]", x):
            return f"不像标签 {x[:20]}"
    return ""


def clean_pat(pats):
    """语法模式列。只留由原书那套记号组成的式子，别的都是 OCR 渣。"""
    out = []
    for p in pats or []:
        p = re.sub(r"[（）]", lambda m: "()"[m.group(0) == "）"], p)
        p = re.sub(r"\s+", " ", p).strip(" ,;.")
        # 斜杠也要当分隔符：`v + n/pron + adv` 里的 `n/pron` 是两个记号，
        # 不拆开整条模式都会被当成 OCR 渣丢掉，全书只剩 `v + prep` 那一种
        toks = [t for t in re.split(r"[\s+()/]+", p) if t]
        if not toks or not all(PAT_OK.match(t) for t in toks):
            continue
        if p not in out:
            out.append(p)
    return out


# 释义英文里拖着的反白标签和交叉引用（`OBJ change, the end of sth`、
# `note at AGREE TO STH`、`SYN cause sth`）。02 只摘得掉行首那些，
# 挤在同一段中间的要在这儿砍掉
TAIL_JUNK = re.compile(
    r"\s*(?:\b[A-Z]{2,5}\]?\b|Io?M\b|DPR\b|EY?A?N\b|Bw?N\b|BXN\b|o[B8]J?\]?\b"
    r"|os\]?\b|sa\b|coc\b|note at\b|\*).*$")


# 语域标签。义项号切开之后每一段的开头还可能挂着标签
# （`2 (informal to show sth`），03 只在整块开头摘过一次，这儿要再摘一遍
LEAD_TAG = re.compile(
    r"^\(?\s*(?:informal|formal|spoken|written|literary|humorous|slang|taboo|"
    r"rare|old-fashioned|disapproving|approving|figurative|especially|"
    r"BrE|AmE|NAmE|AustralE|CanE|IrishE|ScotE|SAfrE)\b[\s,;)]*", re.I)


def clean_en(en):
    """英文释义。尾巴上的标签和交叉引用砍掉，句子本身留着。"""
    en = re.sub(r"\s+", " ", (en or "")).strip()
    en = TAIL_JUNK.sub("", en)
    while True:                       # `(informal (of a drink, a meal, etc.`
        new = LEAD_TAG.sub("", en)
        if new == en:
            break
        en = new
    # 断行连字符：`inter- esting` → `interesting`
    en = re.sub(r"(\w)-\s+(\w)", r"\1\2", en)
    # 形近数字要还原：`used to tell sb rudely to g0 away` 里的 g0 是 go
    en = re.sub(r"[A-Za-z]*\d[A-Za-z\d]*", lambda m: respell(m.group(0)), en)
    # OCR 把小型大写字母认成了大写（`toOl`、`tO`、`suI`）。
    # 全小写之后是个真词就改，不是就留着，让自查把它报出来
    en = re.sub(r"\b[A-Za-z]*[a-z][A-Z][A-Za-z]*\b",
                lambda m: m.group(0).lower()
                if p04.real_word(m.group(0).lower()) else m.group(0), en)
    # OCR 认花的符号：`fail| (`、`brushing ##`、`difficulty if#`
    en = re.sub(r"[{}｜|＊*#＄$@^~`＜＞<>\[\]]+", " ", en)
    # 扫描件把括号吃掉一半是常态，孤立的那个抹掉就好，别整段截断
    en = drop_orphan_paren(en)
    # 义项号残渣（`to A 1 to believe`）和串进来的反白标签残片（`VeT)`）
    en = re.sub(r"(?:^|\s)[A-Z]{1,4}[)\]](?=\s|$)", " ", en)
    en = re.sub(r"(?:^|\s)\d(?=\s|$)", " ", en)
    en = re.sub(r"\s+", " ", en).strip()
    # **收尾不能把左括号也剥掉**：`(of sth) (AmE) to become older…` 的第一个
    # 括号是主语限制，剥了它整句的括号就不配对了（377 处里的绝大多数）
    en = en.strip(" ,;:-")
    # 剩下的只有标签或者一个数字（`BrE also`、`1`），那不是释义
    if len(en) < 8 or not re.search(r"\b(?:to|used|if|when|of)\b", en, re.I):
        return ""
    # 修不好的英文释义整句不要（`to move forward quickly i`、`CtC`）。
    # 中文释义还在，这一行照样有用——比印一句带错字的英文强
    return "" if bad_en(en) else en


# 英文释义里正经会出现的短词。除此之外的孤立单字母/两字母 token 都是渣
EN_TWO_OK = {"a", "an", "as", "at", "be", "by", "do", "go", "if", "in", "is",
             "it", "no", "of", "on", "or", "so", "to", "up", "us", "we", "he",
             "me", "my", "etc", "sb", "sth", "eg", "ie", "am", "are", "you"}


def bad_en(en):
    """英文释义坏在哪儿。原书的释义是一句规规矩矩的英文，
    夹进来的都是反白标签、义项号、和 OCR 认花的符号。"""
    if not en:
        return ""
    if CJK.search(en):
        return "混中文"
    if re.search(r"[{}｜|＊*#＄$@^~`＜＞<>\[\]]", en):
        return "怪符号"
    if en.count("(") != en.count(")"):
        return "括号不配对"
    # `to lose a game VeT) badly`、`to A 1 to believe`：反白标签和义项号串进来了
    if re.search(r"(?:^|\s)[A-Z]{1,4}[)\]]", en):
        return "标签残片"
    # **英文释义里不该有任何数字**。原书的释义是一句解释，数字只会出现在例句里；
    # 出现的全是 OCR 把字母认成了数字（`to not 80 near sb`=go、`a space 30 that`=so、
    # `to agree 10 be`=to）。全书只有 7 处，一律算坏，别为它写还原规则
    if re.search(r"\d", en):
        return "夹数字"
    if re.match(r"^(?:informal|formal|literary|humorous|slang|rare|BrE|AmE)\b", en):
        return "语域标签没摘干净"
    for w in re.findall(r"[A-Za-z][A-Za-z'’]*", en):
        if len(w) <= 2 and w.lower() not in EN_TWO_OK:
            return f"碎渣 {w}"
        if odd_caps(w):
            return f"词中大写 {w}"
    return ""


def bad_zh(zh):
    """例句译文坏在哪儿。它是一句连贯的话，判据跟解释列不一样：
    句号逗号都是正经标点，但括号必须配平、不能拖着重复标点。"""
    if not zh:
        return ""
    if re.search(r"[A-Za-z]{3,}", zh):
        return "混英文"
    if zh != drop_orphan_paren(zh):
        return "括号不配对"
    if re.search(r"[。！？][\s。．.！？；;，,、·•◇○〇]+$", zh):
        return "句末标点重复"
    # `•` 夹在汉字中间是外国人名的间隔号（`斯嘉丽•约翰逊`），正经标点，别误报。
    # 只有落在句末或紧挨着标点的才是例句引导符 ◇ 的残渣
    if re.search(r"(?<=[。！？…])\s*[0oO]\s*[。．.]?$", zh):
        return "句末引导符残渣"
    if re.search(r"[◇○〇◎◆●∘º*|｜［］【】_]", zh) or re.search(
            r"(?<![\u4e00-\u9fff])•|•(?![\u4e00-\u9fff])", zh):
        return "怪符号"
    if not zh.endswith(("。", "！", "？", "”", "）")):
        return "没有句末标点"
    if zh[0] in "，,。.；;、·)）":
        return "开头标点"
    return ""


def bad_cn(cn):
    """中文释义坏在哪儿。判据跟 `09_clean.clean_gloss` 共用。"""
    if not cn:
        return ""
    if re.search(r"[A-Za-z]{2,}", cn):
        return "混英文"
    # 义项号、圆圈数字、罗马数字这类标号一个都不许留——它们在成品里没有参照，
    # 读者只看到一个莫名其妙的「1」
    if re.search(r"[0-9①-⑳ⅠⅡⅢⅣⅤ]", cn):
        return "残留标号"
    if re.search(r"[A-Za-z|｜~～*#$］［【】「」_•◇○〇◎◆●]", cn):
        return "残留碎字"
    if " " in cn:
        return "夹空格"
    if re.search(r"[！!？?]", cn):
        return "怪标点"
    for x in GLOSS_SEP.split(cn):
        x = x.strip(" ·-—")
        if not x:
            continue
        if len(x) == 1 or not CJK.search(x):
            return f"碎渣义项 {x}"
        if x != drop_orphan_paren(x):
            return f"括号不配对 {x}"
    return ""


# 例句里不会原样出现的占位符
PLACE_EX = {"sb", "sth", "sb's", "sth's", "one's", "yourself", "etc", "etc.",
            "sb/sth", "sth/sb"}

def variants(pv):
    """一条短语动词可能写了好几个变体：`ˌswing aˈround; ˌswing sb/sth aˈround`。
    分号（原书用的）和 `(BrE also …)` 都是变体分隔。返回去掉重音和占位符的词序列。"""
    pv = re.sub(r"\((?:BrE|AmE|NAmE)?\s*also\s*", ";", pv)
    out = []
    for part in re.split(r"[;；]", re.sub(r"[ˈˌ]", "", pv)):
        part = re.sub(r"\([^)]*\)?", " ", part)
        ws = [w for w in re.split(r"[\s]+", part.strip())
              if w and w.lower() not in PLACE_EX]
        if ws:
            out.append(ws)
    return out



def bold_ex(text, pv):
    """例句里把整条短语动词加粗，**连小品词一起**。

    先整条短语匹配（`brighten the place up` 要连 the 一起标黑），词之间允许插进
    一两个词——短语动词的宾语就插在中间，这是这本书的常态，不允许插入就几乎
    标不上。整条对不上才退回逐词标。
    """
    for ws in variants(pv):
        parts = []
        for w in ws:
            alts = [inflect(x) for x in w.split("/") if x]
            if not alts:                    # `/` 单独成词（`in/out` 被切碎了）
                continue
            parts.append("(?:" + "|".join(alts) + ")" if len(alts) > 1 else alts[0])
        parts = [p for p in parts if p]
        if not parts:
            continue
        pat = r"[\s,]+(?:\w+[\s,]+){0,3}".join(parts)
        m = re.search(r"\b" + pat + r"\b", text, re.I)
        if m and "<b>" not in m.group(0):
            return text[:m.start()] + f"<b>{m.group(0)}</b>" + text[m.end():]
    for ws in variants(pv):
        for w in ws:
            for x in w.split("/"):
                if len(x) < 3 or x.lower() in FUNCTION:
                    continue
                text = re.sub(rf"(?<![>\w])({inflect(x)})(?!\w)",
                              r"<b>\1</b>", text, flags=re.I)
    # **一个字都没标上就退而标小品词**。`be ˈin for sth` 的三个词全是虚词，
    # 例句 `She's in for a shock.` 里 be 还缩成了 's，整句一处黑都没有，
    # 看着就像忘了标。小品词才是这条短语动词的重点，标它总比不标强
    if "<b>" not in text:
        for ws in variants(pv):
            for x in ws[-1].split("/"):
                if x and x.lower() not in PLACE_EX:
                    text = re.sub(rf"(?<![>\w])({re.escape(x)})(?!\w)",
                                  r"<b>\1</b>", text, count=1, flags=re.I)
                    if "<b>" in text:
                        break
            if "<b>" in text:
                break
    return flatten(text)



def flatten(text):
    """整条标完再逐词标会套出 `<b>put <b>up</b> with</b>`，按深度只留最外层。"""
    out, depth = [], 0
    for tok in re.split(r"(</?b>)", text):
        if tok == "<b>":
            if depth == 0:
                out.append(tok)
            depth += 1
        elif tok == "</b>":
            depth = max(depth - 1, 0)
            if depth == 0:
                out.append(tok)
        else:
            out.append(tok)
    return "".join(out) + "</b>" * (1 if depth else 0)


# 小品词。短语动词一定以**动词**开头，以小品词开头说明动词被切掉了
PARTICLES = {"back", "out", "up", "off", "in", "on", "away", "down", "over",
             "through", "around", "round", "along", "across", "apart", "aside",
             "forward", "together", "by", "to", "for", "with", "into", "onto",
             "upon", "at", "from", "of", "about", "after", "against", "ahead",
             "behind", "beyond", "between", "under", "without", "past", "off"}
# 短语动词的第一个词就是它的动词。占位符和说明词要跳过
PV_SKIP = {"sb", "sth", "one", "ones", "yourself", "also", "esp", "especially",
           "usually", "informal", "formal", "not", "sbs", "sths"}


def variant_spelling(a, b):
    """英美拼写变体：等长、首字母相同、最多差两个字母（`bale`/`bail`、
    `armour`/`armor` 不等长走 close）。`close` 卡不住 `bale`/`bail`——
    它俩差两处又不是相邻换位，会被当成两个不同的词，凭空多出一个 `bale` 词条。"""
    if len(a) != len(b) or len(a) < 4 or a[0] != b[0]:
        return False
    return sum(x != y for x, y in zip(a, b)) <= 2


def head_of_pv(pv):
    """短语动词的动词（第一个实义词）。"""
    for tok in re.findall(r"[A-Za-z][A-Za-z']*", plain_pv(pv)):
        if tok.lower() not in PV_SKIP:
            return tok.lower()
    return ""


def fix_pv_word(pv, word):
    """让**短语动词和它的词头对得上**，返回 (短语动词, 词头) 或 None。

    这本书里词头对不上有三种情形，全书 426 条（8.7%）：

    1. **词头行被 OCR 整行吞掉**，后面十几条全挂到上一个词头名下
       （`back ˈup`、`back ˈdown`、`ˈbackup n` 十二条挂在 `awaken` 底下）。
       短语动词的**第一个词就是它的动词**，比搭配词典那种「整组统计」硬得多——
       直接拿它当词头认回来。
    2. **拼写变体**：`bail` 词条下写的是 `ˌbale ˈout`（bale 是 bail 的英式拼法）。
       跟词头差一个字母的，改成词头，别另开一个 `bale` 词条。
    3. **条目被腰斩，动词整个没了**：`ˈout of sth (informal)`、`sb's beˈhalf)`、
       光一个 `sth`。补不回来（语序和动词都没了），整条丢掉。
    """
    lead = head_of_pv(pv)
    stem = word.lower()[:max(3, len(word) - 2)]
    if stem in plain_pv(pv).lower():
        return pv, word
    if not lead or len(lead) < 2 or lead in PV_SKIP:
        return None                      # 情形 3：压根没有动词
    if close(lead, word) or variant_spelling(lead, word):
        # 情形 2：拼写变体（`bale`/`bail`），改成词头，别另开一个词条
        # **不能用 `\b`**：重音符号 ˈ ˌ 在 Unicode 里是「修饰字母」，算 `\w`，
        # 所以 `ˌbale` 里的 bale 前面没有词边界，替换根本不发生
        # 变体拼写要**全部**换掉：`ˌbale ˈout, bale ˈout of sth` 里有两处
        return re.sub(rf"(?<![A-Za-z]){re.escape(lead)}(?![A-Za-z])",
                      word, pv, flags=re.I), word
    if lead in PARTICLES:
        # 动词被切掉了，剩下的以小品词打头（`ˈback (from doing sth)` 其实是
        # `shrink back from doing sth` 那一类）。拿 `back` 当词头就全错了
        return None
    if bad_head(lead):
        return None                      # 认回来的也不是个词，整条不要
    return pv, lead                      # 情形 1：拿条目里的动词当词头


def iter_rows(rows):
    """把 `data/rows.json` 过一遍清洗，产出成品里真正要印的行。

    **渲染和自查都走这个函数**，不许各抄一份——搭配词典上栽过：
    两边口径一旦分叉，自查报的 0 就是假的。

    产出 `(词头, 短语动词, 模式, 标签, 中文释义, 英文释义, 例句列表)`。
    """
    # 认回来的词头必须**排得进字母序**，否则就是认错了。`head_of_pv` 拿条目的
    # 第一个词当动词，条目被 OCR 弄坏时会拿到 `sb's`、`curtain`、`themselves`
    # 这种东西。判据要**两边都卡**：既不能小于上一个印出来的词头，也不能大于
    # 后面第一个「原书自己的词头」——只卡左边的话 `curtain` 插在 bring 和
    # broaden 之间照样过得去。原书自己的词头不用查，02 的最长不下降子序列筛过了
    nxt, later = [None] * len(rows), None
    for i in range(len(rows) - 1, -1, -1):
        nxt[i] = later
        later = rows[i]["word"] if later is None or rows[i]["word"] != later \
            else later
    prev, seen = None, set()
    for i, r in enumerate(rows):
        for s in r["senses"]:
            row = clean_row(r["pv"], r["pats"], r["tags"],
                            s["cn"], s["en"], s["ex"], r["word"])
            if row is None:
                continue
            word = row[0]
            if word != r["word"] and (
                    (prev and word < prev) or (nxt[i] and word > nxt[i])):
                continue
            key = (word, row[1], row[4])      # 同一个 词头+条目+释义 只印一次
            if key in seen:
                continue
            seen.add(key)
            prev = word
            yield row


def clean_row(pv, pats, tags, cn, en, ex, word):
    """一行。短语动词坏了返回 None，整行不印。

    `ex` 是 [(英, 中)]。例句一条条过 `clean_ex`，过不了的丢掉，
    **不许留空格子**：一条例句都不剩的行整行不要。
    """
    pv = clean_pv(pv)
    if bad_pv(pv):
        return None
    fixed = fix_pv_word(pv, word)
    if fixed is None:
        return None
    pv, word = fixed
    cn = clean_cn(cn)
    en = clean_en(en)
    # **没有中文释义的行不印**。这本是给中文读者查的，释义格里只有一句英文
    # 等于这一行没做完；宁可少印一行，也不印半成品
    if not cn:
        return None
    keep = []
    for a, b in ex or []:
        a2, b2 = clean_ex([plain_pv(pv)], a, b)
        # **一个字都标不粗的例句，多半根本不是这条的例句**
        # （`ˈgo at sth` 底下挂着 `Go away and think about it.`）。
        # 加粗比 `bad_sentence` 里的「任一实词命中」严得多，是最后一道对账
        if a2 and "<b>" in bold_ex(a2, pv):
            keep.append([a2, b2])
    if not keep:
        return None
    return word, pv, clean_pat(pats), clean_tags(tags), cn, en, keep
