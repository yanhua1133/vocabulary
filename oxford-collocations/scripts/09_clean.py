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
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

_spec = importlib.util.spec_from_file_location("p04", os.path.join(HERE, "04_expand.py"))
p04 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p04)

CJK = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")
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
OK_CHARS = re.compile(r"^[A-Za-z0-9 '’/()\[\]\-,.&!?+*~%$£€°]*$")
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
    return not p04.real_word(low) and z(low, "en") < 3.0


# 原书写在搭配后面的括号注解：`(= the right to live in a place)`。
# 那是释义，不该占搭配格；而且扫描件常把右括号吃掉，留个半拉括号在那儿
GLOSS = re.compile(r"\(=[^)]*\)?")
# 中文标点混进英文里：`～` `⋯` 是原书的省略号和词头占位符，去掉就好；
# `。，、《》` 这类是切分切错了地方，救不回来
CN_FILLER = re.compile(r"[～〜~⋯…·•◆◇＊]")
CN_PUNCT = re.compile(r"[。，、；：！？（）《》「」【】]")


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
    return p


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
    # `a 16-digit number`、`the 22nd amendment` 里的数字是正经的
    if re.search(r"\d", p) and not re.fullmatch(
            r"[^\d]*\d+(?:-\w+|st|nd|rd|th|%|s)?[^\d]*", p):
        return "夹数字"
    # 书里的逗号被扫成了句点，`growing, increasing` 成了 `growing. increasing`，
    # 两条搭配黏成一条。切不回去，整行丢掉
    if re.search(r"[a-z]\.\s+[a-z]", p):
        return "两条黏一起"
    words = p.split()
    if len(words) > 9 or (re.search(r"[?!]", p) and len(words) > 5):
        return "其实是句子"
    if SUBJ.search(p) or LEAD_SUBJ.match(p):
        return "其实是句子"
    # 首字母被吃掉，剩个孤零零的字母：`n accepting`、`t wil`、`s this`。
    # a 和 I 是正经的（`a matter of time`、`I bet`）
    if re.search(r"(?:^|\s)[b-hj-z](?:\s|$)", p, re.I):
        return "缺首字母"
    for w in re.findall(r"[A-Za-z][A-Za-z'’]*", p):
        if bad_word(w):
            return f"坏词 {w}"
    return ""


def bad_head(word):
    """词头坏没坏。查不到的词条一点用没有，整条不要——
    `thanktul adj` 这种词头，读者按 thankful 翻永远翻不到。"""
    return (not word or not re.fullmatch(r"[A-Za-z][A-Za-z' \-]*", word)
            or bad_word(word))


def clean_cn(cn):
    """解释列。OCR 常把隔壁栏的英文搭配和例句卷进来：

        电蓄热器 1 battery (AmE) 蓄电池
        薪金上调;工资的上涨 1 budget, dividend, fare, pr

    中文解释里本来就不该有成串的英文，所以**从第一处英文起整段截掉**，
    留下前面那截干净的中文。截完只剩标点就当空。
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
    cn = re.sub(r"\s+", "", cn).strip(" ,.;:、，。；：·-—")
    return cn if CJK.search(cn) else ""


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


def clean_ex(full, en, zh):
    """例句列。修不好就整条不要——宁可这行没例句，也不能印半句。"""
    en = re.sub(r"\s+", " ", (en or "").replace("’", "'").strip())
    zh = re.sub(r"\s+", " ", (zh or "").strip())
    plain = re.sub(r"</?b>", "", en)
    if not plain:
        return "", ""
    words = content_words(full[0])
    ok = (plain[:1].isupper() and len(plain.split()) >= 5
          and plain.rstrip().endswith((".", "!", "?", "'", '"', "’", "”"))
          and not CJK.search(plain)
          and not MARKER.search(plain)
          and OK_CHARS.match(plain)
          # 交叉引用被卷进来了：`Special page at BUSINESS arrangement with a`
          and not any(t.isupper() and len(t) >= 3 and t not in CAPS_OK
                      for t in re.findall(r"[A-Za-z]{2,}", plain))
          and not any(bad_word(w) for w in re.findall(r"[A-Za-z][A-Za-z'’]*", plain))
          # 例句得真的在讲这条搭配。一个词都对不上就是归错了小类
          and (not words or any(hits(w, plain) for w in words)))
    if not ok:
        return "", ""
    return en, clean_cn(zh)


def clean_row(full, cn, en, zh):
    """一行四列。搭配全坏就返回 None，整行不印。"""
    keep = [x for x in (norm_phrase(f) for f in (full or [])) if not bad_phrase(x)]
    if not keep:
        return None
    en, zh = clean_ex(keep, en, zh)
    return keep, clean_cn(cn), en, zh


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
