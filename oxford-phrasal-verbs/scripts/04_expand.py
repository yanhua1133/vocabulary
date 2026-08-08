"""Pass 04: 把小类里的搭配词展开成完整搭配 → data/expanded.json。

原书为了省地方，搭配词只写不重复的那半截，词头用 `~` 代替或者干脆省掉：

    abandon verb → ADV. hastily          其实是 hastily abandon
                 → PHRASES ~ sb to their fate   其实是 abandon sb to their fate
    agreement noun → ADJ. draft          其实是 draft agreement
                   → VERB + AGREEMENT negotiate   其实是 negotiate an agreement

查着不方便，全部补成完整形式，`~` 也一律换回词头。补的方向按组类型定：
形容词、副词、`VERB + 名词` 都是搭配词在前，`名词 + VERB` 反过来，
`QUANT.` 要加个 of，介词组看词头是动词还是名词。

Usage: 04_expand.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


# 形近字母对。前一批修完还剩 2886 处，看剩下的样子补出来的：
# lefeat→defeat、tirm→firm、readquarters→headquarters、vork→work
CONFUSE = {"i": "l", "l": "i", "t": "l", "f": "l", "o": "c", "c": "o",
           "a": "o", "u": "n", "n": "u", "e": "c", "h": "b", "y": "v",
           "rn": "m", "ii": "u", "1": "l", "0": "o",
           "l": "d", "d": "l", "t2": "f", "f2": "t", "r": "h", "h2": "r",
           "v": "w", "w": "v", "c2": "d", "g": "q", "q": "g", "s": "g"}
# 展平成 (错, 对) 的列表——字典的 key 不能重复，同一个字母有好几种认错方向
PAIRS = [("i", "l"), ("l", "i"), ("t", "l"), ("f", "l"), ("o", "c"), ("d", "c"),
         ("c", "s"), ("h", "b"), ("b", "h"), ("k", "b"), ("j", "i"),
         ("c", "o"), ("a", "o"), ("u", "n"), ("n", "u"), ("e", "c"),
         ("h", "b"), ("y", "v"), ("rn", "m"), ("ii", "u"), ("1", "l"),
         ("0", "o"), ("l", "d"), ("d", "l"), ("t", "f"), ("f", "t"),
         ("r", "h"), ("h", "r"), ("v", "w"), ("w", "v"), ("c", "d"),
         ("g", "q"), ("q", "g"), ("s", "g"), ("m", "rn")]
_CACHE = {}
# 系统词表（web2）。**光靠词频判不出坏词**：`wil` 的 zipf 有 3.28，比 `ife`(2.69)
# 还高，所以 `it wil work` 怎么都修不掉。查词表一眼就知道它不是英语单词。
# 反过来词表也不够用——1913 年的韦氏，没有 email/website，屈折形式也缺一大半，
# 所以两条判据要合起来：**词表里没有、词频又不高，才算坏词**。
_REAL = None
_REAL_CACHE = {}
WORDS_TXT = "/usr/share/dict/words"
# web2 只收词根，屈折形式得自己还原：emaciated→emaciate、misgivings→misgiving、
# mystified→mystify、empirically→empirical。不还原就会把 60 处 emaciated
# 当成 OCR 错字，整行丢掉
SUFFIX = [("s", ""), ("es", ""), ("ies", "y"), ("ed", ""), ("ed", "e"),
          ("ied", "y"), ("ing", ""), ("ing", "e"), ("ly", ""), ("ally", "al"),
          ("ably", "able"), ("ibly", "ible"), ("er", ""), ("er", "e"),
          ("est", ""), ("est", "e"), ("ness", ""), ("ers", ""), ("ings", "")]
# 英式拼写 → web2 收的美式：woollen→woolen、favourably→favorably、
# exorcize→exorcise、travelled→traveled。
# **只做 ll→l 这一个方向**。反过来写成 l→ll 会把 `wil` 变成 `will` 认成好词，
# `it wil work` 就永远修不掉了——这正是用户点名的那条。
SPELL = [("our", "or"), ("ise", "ize"), ("ize", "ise"), ("isation", "ization"),
         ("yse", "yze"), ("ll", "l"), ("re", "er"), ("ae", "e"), ("oe", "e")]
# 少写一个 l 的英式词就那么几个，列出来，别用通配规则
BRIT_L = {"instil", "skilful", "wilful", "fulfil", "enrol", "distil", "appal",
          "annul", "extol", "enthral", "instalment", "enrolment", "fulfilment",
          "instil", "counsellor", "marvellous"}


def real_word(w):
    """是不是一个正经英语词。三条路都认：词表、词频、还原成词表里的形式。"""
    from wordfreq import zipf_frequency as z
    global _REAL
    if _REAL is None:
        try:
            _REAL = {x.strip().lower() for x in open(WORDS_TXT)}
        except OSError:
            _REAL = set()
    w = w.lower().strip("'’")
    if w in _REAL_CACHE:
        return _REAL_CACHE[w]
    _REAL_CACHE[w] = out = _real(w, z)
    return out


def _real(w, z):
    if len(w) < 3 or w in _REAL or w in BRIT_L or z(w, "en") >= 3.5:
        return True
    if w.endswith("'s") or w.endswith("’s"):          # coroner's、tear's
        return real_word(w[:-2])
    if "-" in w:                                       # 连字符复合词逐段看
        return all(real_word(p) for p in w.split("-") if p)
    for suf, rep in SUFFIX:
        # 递归剥：floorboards → floorboard（合成词）→ 真
        if w.endswith(suf) and len(w) - len(suf) + len(rep) >= 3:
            if real_word(w[:-len(suf)] + rep):
                return True
    # 双写辅音再加后缀：bogged→bog、shopping→shop
    m = re.fullmatch(r"(.*?)([bcdfglmnprstz])\2(ed|ing|er|est|y)", w)
    if m and (m.group(1) + m.group(2)) in _REAL:
        return True
    for a, b in SPELL:
        cand = w.replace(a, b)
        if cand != w and cand in _REAL:
            return True
    # 合成词：minefield、boardroom、suntan、floorboard。两半都得是常用词，
    # 不然 `latural` 会被拆成 lat + ural 蒙混过去
    for i in range(3, len(w) - 2):
        if w[:i] in _REAL and w[i:] in _REAL \
                and z(w[:i], "en") >= 3.0 and z(w[i:], "en") >= 3.0:
            return True
    return False


def _cands(out):
    """给出 (候选, 加分)。加分是**先验**：这本扫描件吃的几乎全是行首的 `l`
    （ocal/argely/ikely/aunch/anguage 都是），所以补 `l` 的候选先加 0.6，
    不然 `ife` 会卡在 life(5.89) / wife(5.23) 分不出高下，白白丢掉整行。"""
    for c in "abcdefghijklmnopqrstuvwxyz":           # 首/尾字母被吃掉
        yield c + out, 0.6 if c == "l" else 0.0
        yield out + c, 0.0
    for i in range(len(out)):                        # 形近认错
        for a, b in PAIRS:
            if out[i:i + len(a)] == a:
                yield out[:i] + b + out[i + len(a):], 0.0
    for i in range(len(out)):                        # 多认了一个字母
        if len(out) > 3:
            yield out[:i] + out[i + 1:], 0.0


def fix_token(w):
    """搭配词里的 OCR 错字。扫描件左边缘常把首字母吃掉，尤其是 `l`——
    `ocal`→local、`argely`→largely、`ikely`→likely、`aunch`→launch、
    `anguage`→language，全书 6911 处。也有形近认错的（`lefeat`→defeat）。

    只在原词不是英语单词、且候选**唯一**又明显更常见时才改。
    候选打平就别猜：`ost` 可能是 lost/cost/most/post，猜错比留着更糟——
    原样留着，`09_clean.py` 会认出它是坏词，把整行丢掉。
    """
    from wordfreq import zipf_frequency as z

    if w in _CACHE:
        return _CACHE[w]
    out = w.lower()
    # 数字混进单词里是 OCR 认错，不是真数字：g00d→good、detedt→detect。
    # 原来先 isalpha() 再纠错，这类词一进来就被挡在门外了
    if re.search(r"[0135]", out) and re.search(r"[a-z]", out):
        digits = str.maketrans("0135", "olse")
        cand = out.translate(digits)
        if z(cand, "en") > z(out, "en") + 1.0:
            out = cand
    # 迭代两轮：有些词错了两处，`ciress` 得先删掉多认的 i 变 cress、再把 c 认回 d
    for _ in range(2):
        base = z(out, "en")
        # 两条判据都要过才算好词：词表里有、而且不算生僻。web2 收了一堆
        # `ife`、`ost` 这样的偏僻词条，只查词表会把丢首字母的词放过去
        if not out.isalpha() or len(out) < 3 or (real_word(out) and base >= 3.0):
            break
        seen = {}
        for c, bonus in _cands(out):
            if len(c) < 3 or c == out or not real_word(c):
                continue
            s = z(c, "en") + bonus
            if s > base + 1.0:
                seen[c] = max(seen.get(c, 0), s)
        good = sorted(seen.items(), key=lambda kv: -kv[1])
        # 候选打平就别猜，留着让 09_clean 整行丢掉
        if not good or (len(good) > 1 and good[0][1] - good[1][1] < 0.8):
            break
        out = good[0][0]
    out = (out.capitalize() if w[0].isupper() else out) if out != w.lower() else w
    _CACHE[w] = out
    return out


# 丢了首字母之后剩下的那个字母 → 它原本是什么词。
# wordfreq 只有单词频率、比不了词组，`in` 和 `an` 分不出高下，所以直接写死。
# 这几个是扫描件左边缘最常吃掉的：介词、系动词、代词
LONE = {"n": "in", "m": "am", "t": "it", "s": "is", "f": "of", "e": "be",
        "y": "by", "o": "to", "r": "or", "g": "go", "p": "up"}


def fix_lone_letter(t):
    """补回被吃掉的首字母：`n accepting the award`（in）、`m expecting a call`（am）、
    `t stayed hot`（it）、`s this an appropriate time`（is）。"""
    def one2(m):
        got = LONE[m.group(1).lower()]
        # 别把 `o to` 补成 `to to`
        return m.group(0) if got == m.group(2).lower() else f"{got} {m.group(2)}"

    # 后面跟的词两个字母就够——`t is accountable` 里的 is 只有两个字母，
    # 卡三个字母会把这一大类（341 条）全放过去
    # 前面必须是空格或行首。用 \b 会把 `couldn't believe` 里的 t 当成孤立字母，
    # 补成 `couldn'it believe`
    return re.sub(r"(?<![\w'’])([%s])\s+([a-z]{2,})" % "".join(LONE), one2, t)


def fix_phrase(t):
    # OCR 爱在缩写的撇号后面多塞个 i：don'it / couldn'it / isn'it
    t = re.sub(r"n'i?t\b", "n't", t)
    # 连字符要拆开分别修：`ife-support` 整体查不到词频，拆成 ife / support
    # 才认得出 ife 少了个 l
    # 字符集要带上数字，`g00d`、`detedt` 这类混了数字的词否则根本进不了纠错
    t = fix_lone_letter(t)
    return re.sub(r"[a-zA-Z][a-zA-Z0-9']{2,}",
                  lambda m: fix_token(m.group(0)), t)


def split_words(s):
    """搭配词串切成一个个词。按逗号切；`/` 是同一个词的两种拼法，不能切。"""
    out = []
    for p in re.split(r"[,;]", s):
        p = p.strip(" .·、")
        p = re.sub(r"\s+", " ", p)
        if p and not re.fullmatch(r"(etc\.?|and|or|also)", p, re.I):
            out.append(p)
    return out


def put_head(w, head):
    """把 `~` 换回词头。`~ed` `~ing` `~s` 是词形变化，要按拼写规则变，
    不能直接拼——`be found~ed` 硬拼出来是 `be foundabandoned`。"""
    def form(m):
        # 词尾大小写要归一：原书印的是小型大写字母，OCR 读成 `~S`，
        # 直接拼出来就是 `fallen logS`
        suf = (m.group(1) or "").lower()
        vowel_y = len(head) > 1 and head[-1] == "y" and head[-2] not in "aeiou"
        if suf in ("ed", "d"):
            if vowel_y:
                return head[:-1] + "ied"
            return head + ("d" if head.endswith("e") else "ed")
        if suf == "ing":
            return (head[:-1] if head.endswith("e") else head) + "ing"
        if suf in ("s", "es"):
            if vowel_y:                            # ability + ~s → abilities
                return head[:-1] + "ies"
            if re.search(r"(s|x|z|ch|sh)$", head):
                return head + "es"
            return head + "s"
        return head + suf

    w = re.sub(r"(?<=[a-zA-Z])~", " ~", w)         # OCR 常把 ~ 前的空格吃掉
    # `~of` 里的 of 是下一个词不是词尾，不隔开会拼成 `canof`
    w = re.sub(r"~(?!(?:ing|ed|es|s|d)\b)(?=[a-z])", "~ ", w)
    return re.sub(r"~(ing|ed|es|s|d)?", form, w, flags=re.I)


def expand_one(w, head, gtype, pos):
    """一条搭配词补成完整搭配。"""
    if "~" in w:                                   # 原书已经标了词头的位置
        return put_head(w, head)
    t = gtype.upper()
    if t.startswith("QUANT"):
        return f"{w} of {head}"
    if "+ VERB" in t or t.startswith("NOUN +"):    # 名词在前、动词在后
        return f"{head} {w}"
    if t.startswith("PREP"):
        # 介词组：动词词头是 `abandon for`，名词词头是 `in agreement`
        return f"{head} {w}" if pos == "verb" else f"{w} {head}"
    if t.startswith("PHRASE"):
        return w if head in w else f"{head} {w}"
    return f"{w} {head}"                            # ADJ. / ADV. / VERB + 名词


def bold(text, head, phrases):
    """例句里把讨论的搭配标粗：词头（含被写成 ~ 的）和搭配词都要标。"""
    if not text:
        return text
    out = re.sub(r"(?<=[a-zA-Z])~", " ~", text)
    out = re.sub(r"~(ing|ed|es|s|d)?",
                 lambda m: f"<b>{put_head('~' + (m.group(1) or ''), head)}</b>",
                 out, flags=re.I)
    stem = head[:-1] if len(head) > 4 and head.endswith("e") else head
    out = re.sub(rf"(?<![>\w]){re.escape(stem)}(\w{{0,3}})(?!\w)",
                 rf"<b>{stem}\1</b>", out, flags=re.I)
    for p in phrases:
        w = p.split()[0]
        if len(w) < 4 or w.lower() == head.lower():
            continue
        out = re.sub(rf"(?<![>\w]){re.escape(w)}(\w{{0,3}})(?!\w)",
                     rf"<b>{w}\1</b>", out, count=1, flags=re.I)
    return re.sub(r"</b>(\s*)<b>", r"\1", out)      # 相邻的粗体并起来


def clean_cn(t, head):
    """解释列只留中文释义：`~` 换回词头，英文句子、残留标记一律清掉。"""
    t = put_head(t, head)
    # 整句英文是没摘干净的例句
    t = re.sub(r"[A-Z][^\u4e00-\u9fff]{12,}?(?:[.!?]|(?=[\u4e00-\u9fff]))", " ", t)
    t = re.sub(r"[a-zA-Z][a-zA-Z'\-]{2,}(?:\s+[a-zA-Z'\-]{2,}){2,}", " ", t)
    t = re.sub(r"[•◎○●※◇*|]+", " ", t)
    t = re.sub(r"\s*[,;]\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip(" ,;·|")


TYPE_WORD = {"verb", "noun", "adj", "adv", "prep", "phrases", "phrase",
             "quant", "brе", "ame"}


def sense_head(sense, word):
    """义项真正的词头。**组类型行里写着**：`VERB + LOG` 说明这一段讲的是 log。

    扫描件常把词头那一行整行吃掉，后面几个义项就顺延挂到了上一个词条名下——
    `locust` 底下挂着 log / logic / logo 三个词的搭配，印出来是
    `cut locust 砍下的原木`，看着像模像样其实全错。

    两道闸：认回来的词得是**正经英语词**（`ANTIBIOTICBE` 这种 OCR 渣不算），
    而且得**排在词条名后面**——原书按字母序，丢掉的词头只可能在后面。
    """
    for g in sense.get("groups", []):
        for m in re.findall(r"\b([A-Z][A-Z'\-]{2,})\b", g.get("type", "")):
            n = m.lower()
            if n in TYPE_WORD or n.startswith(word[:4].lower()):
                continue
            if len(n) >= 3 and n > word.lower() and real_word(n):
                return n
    return word


def main():
    book = json.load(open(os.path.join(DATA, "groups.json")))
    total = 0
    moved = 0
    for h in book:
        pos = h.get("pos", "")
        for s in h["senses"]:
            head = sense_head(s, h["word"])
            if head != h["word"]:
                moved += 1
                s["head"] = head
            for g in s["groups"]:
                for sub in g.get("subs", []):
                    full = [fix_phrase(expand_one(w, head, g["type"], pos))
                            for w in split_words(sub["words"])]
                    sub["full"] = full
                    sub["cn"] = clean_cn(sub["cn"], head)
                    total += len(full)
                for sub in g.get("subs", []):
                    # 例句必须是完整句：够长、以句末标点收尾
                    sub["ex"] = [[bold(put_head(en, head), head, sub.get("full") or []),
                                  put_head(cn, head)]
                                 for en, cn in sub.get("ex", [])
                                 if len(en.split()) >= 4 and en.rstrip().endswith((".", "!", "?"))]

    json.dump(book, open(os.path.join(DATA, "expanded.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"展开出 {total} 条完整搭配；按组类型认回词头的义项 {moved} 个")
    for h in book[:1]:
        for s in h["senses"][:1]:
            for g in s["groups"][:2]:
                print(f"  [{g['type']}]", " / ".join(
                    w for sub in g["subs"] for w in sub["full"])[:76])


if __name__ == "__main__":
    main()
