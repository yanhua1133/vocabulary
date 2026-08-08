"""Pass 09: 成品清洗。渲染前每一行过一遍：**能修的修，修不了的整行不要**。

这本是纯扫描件，OCR 之后总有一批格子怎么修都修不回去——半句正文被当成搭配、
组类型标记（`ADJ.` `VERB + NOUN`）串进搭配里、中文注释混进英文里。
以前的做法是照印不误，结果词表里明晃晃摆着

    n accepting the award work        （其实是例句 In accepting the award...）
    it wil work                       （wil 是 will 掉了一个 l）
    admission rates /ERB + ADMISSION app for seek

**宁可少印一行，也不能印错一行**：搭配列修不好就整行丢掉；
解释和例句列修不好就留空，行还留着——搭配本身是对的，值得印。

判据全部对应真实犯过的错，跟 `08_audit.py` 共用一套，
所以自查数字能真的跑到 0，而不是自己查自己。

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
OK_CHARS = re.compile(r"^[A-Za-z0-9 '’/()\[\]\-,.&!?+~%$£€°]*$")
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
    if len(low) <= 4 and z(low, "en") < 3.5 and low not in SHORT_OK:
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


def clean_gloss(t):
    """解释列专用：切成义项，逐条判，句子混进来的整条扔掉。

    OCR 常把例句译文和下一个小类的义项一起卷进解释格，成品里就是
    `狠狠的！使劲的；用力的；…；凶猛的一踢 。(这个城市需要好好鞭策一下。空手道脚法`
    这种一路吃到隔壁的怪东西。逐条判比整段截断稳——
    `习得力。培养；增强；提高能力` 从句号处截会白丢三条正经义项。
    """
    t = drop_orphan_paren(t.replace("⋯", "…"))
    # 方括号、下划线、竖线这些是 OCR 把版面符号认了进来（`评论界的赞扬 ］`、
    # `道义责任 _`）。省略号前后的空格和后面拖的句点也一起抹掉（`…. 缺席期间`）
    t = re.sub(r"[］［【】「」〔〕〈〉_]", " ", t)
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
    cn = re.sub(r"[~～*#$%^&<>\\/\[\]{}]", " ", cn)
    # 书里用竖线分隔两条解释，扫成了 `1` `I` `l`；剩下的孤立字母数字也是碎渣。
    # 位置不限——`施虐者1受虐者`、`培养增强提高能力1` 都要清掉，
    # 卡「前后不是汉字」的话紧贴汉字的这些一个也清不掉
    cn = re.sub(r"[0-9A-Za-z|｜]+", "；", cn)
    cn = re.sub(r"[；;]\s*(?=[；;])", "", cn)
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
    if not plain[:1].isupper() or len(plain.split()) < 5:
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
    if zh and not zh.endswith(("。", "！", "？", "”", "）")):
        zh += "。"
    return en, zh


def wrong_head(word, phrases):
    """整组搭配被填错了词头时，返回被错填进去的那个词，否则返回空串。

    `04_expand.py` 展开 `~` 时偶尔取到**字母序上相邻的下一个词头**：
    abortion 组里填的是 abscess、ask 填成 aspect、bail 填成 ball、
    bachelor 填成 back。全书 4312 条（2.6%）。

    判据是「组内几乎每条都含同一个词，而那个词不是本组词头」——
    单看一条分不出来（`have abscess` 本身是通顺的），得看整组。
    """
    if len(phrases) < 3:
        return ""
    stem = word.lower()[:max(3, len(word) - 2)]
    if sum(1 for p in phrases if stem in p.lower()) / len(phrases) > 0.5:
        return ""
    c = collections.Counter()
    for p in phrases:
        c.update(set(re.findall(r"[a-z]{3,}", p.lower())))
    top, n = c.most_common(1)[0]
    return top if n / len(phrases) > 0.6 and top != word.lower() else ""


def clean_row(full, cn, en, zh):
    """一行四列。搭配全坏就返回 None，整行不印。"""
    keep = [x for x in (norm_phrase(f) for f in (full or [])) if not bad_phrase(x)]
    if not keep:
        return None
    en, zh = clean_ex(keep, en, zh)
    cn = clean_cn(cn)
    # 解释空了就整行不要。**不许有空白单元格**——没有解释的行读者只看到
    # 一条搭配和一个空格子。解释被 `clean_gloss` 判成整格都是句子残渣时
    # （`她已将账户中的钱都取走`）也走这条路，宁可少印一行也不印空格子
    if not cn or not en:
        return None
    return keep, cn, en, zh


def main():
    spec = importlib.util.spec_from_file_location("p07", os.path.join(HERE, "07_render.py"))
    p07 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p07)
    book = json.load(open(os.path.join(DATA, "expanded.json")))
    why = {}
    n = drop = 0
    for h in book:
        for s in h["senses"]:
            for g in s["groups"]:
                for sub in g.get("subs") or []:
                    full = [norm_phrase(p04.fix_phrase(x))
                            for x in (sub.get("full") or [])]
                    if not full:
                        continue
                    n += 1
                    reasons = [bad_phrase(f) for f in full]
                    if all(reasons):
                        drop += 1
                        r = re.sub(r" .*", "", reasons[0])
                        why.setdefault(r, []).append(full[0])
    print(f"{n} 行，丢掉 {drop} 行（{drop / n:.1%}）")
    for r, xs in sorted(why.items(), key=lambda kv: -len(kv[1])):
        print(f"  {r}: {len(xs)}")
        for x in xs[:5]:
            print(f"      {x[:70]}")


if __name__ == "__main__":
    main()
