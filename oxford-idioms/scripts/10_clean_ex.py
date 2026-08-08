"""Pass 10: 清理从扫描件抽出来的原书例句 → data/examples.json。

原书例句是词典的权威内容，能用就该用，只有确实被 OCR 毁掉的才退回自写例句。
抽出来的 5257 条里大部分是干净的，坏的是些固定套路：

- `T've` / `Tm` → `I've` / `I'm`（大写 I 被认成 T）
- `Im` / `Il` → `I'm` / `I'll`（撇号丢了）
- `WaS`、`tHe` 这类词中间冒出大写字母
- 中文里插进空格、英文数字与汉字之间缺空格
- 句子被截断（没有结尾标点、或以介词冠词收尾）

Usage: 10_clean_ex.py
"""
import collections
import json
import os
import re

from wordfreq import zipf_frequency

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CJK = re.compile(r"[\u4e00-\u9fff]")   # .findall 数汉字，.search 判有无
TRUNC = re.compile(r"\b(a|an|the|of|to|in|on|at|for|with|and|or|from|by|"
                   r"that|his|her|my|your|their|is|are|was|were)$", re.I)

# 扫描件常见的形近误认。数字占大头（go→g0、good→g00d、look→100k），也有字母
# （again→qgain）。不列替换表（列多少漏多少），而是按形近逐个回代、再验一遍是不是真词
CONFUSE = {"0": "o", "1": ["l", "i"], "2": ["z", "a"], "3": "e", "4": "a",
           "5": "s", "6": "b", "7": "t", "8": ["g", "b"], "9": "g",
           "q": "a", "|": "l", "l": "i", "i": "l"}
# 纯数字的词（go→80、zoo→200、look→100k）跟真数字长得一模一样，光看词形分不出来，
# 只能靠句法位置判：数字落在动词位/限定词后面时，它一定不是数字。
# 前面是 to/you/has 这类 → 动词位，还原成词；前面是 she/of/the 这类 → 名词位，
# 这些句子多半已经被 OCR 搅烂（`She 248 was fortunate`），交给 usable() 整条弃用
VERB_SLOT = re.compile(r"\b(to|you|we|they|usually|has|have|had|ll|will|would|"
                       r"must|can|could|should|not|never|and)(\s+)80\b(?=\s+[a-z])",
                       re.I)
DET_SLOT = re.compile(r"\b(she|he|it|its|they|we|and|or|but|your|my|his|her|"
                      r"the|of)\s+\d+\b(?=\s+[a-z])", re.I)
DET_FIX = {"200": "zoo", "825": "gas", "180": "I go"}
AFTER_IF = set("you he she they we it i not there this that".split())
IRREG = {}          # 由 07_render 在 import 后灌进来，避免两处各维护一张表
# 条目里的占位成分和虚词，不能拿它们判断例句有没有用上这条习语
PLACEHOLDER = set("""sth sbs sb one ones etc doing does done being your yours
    that this with have has had been from into them they their his her its our
    and the for but not you who whom whose all any some such very
    also both each""".split())
# 混进例句的音标残片：`bending my ear all berth /b3:0;AmE b3:zre/ night`。
# 只认真的音标（带长音号、AmE 标注或音标专用字母），别误删正常的 and/or 斜杠
IPA_FRAG = re.compile(r"\s*/[^/]{2,60}/\s*")
IPA_SIGN = re.compile(r"[ɑɒəɜɪʊʌæŋʃʒθðˈˌ]|:|AmE|BrE")
# 判「这个词还带着 OCR 没修掉的数字」。真数字要放行：1950s、42nd、£6 000、9/11
NUMERIC = re.compile(r"^[£$€]?\d[\d,./]*(st|nd|rd|th|s|k|m|bn|am|pm)?$", re.I)
HASDIGIT = re.compile(r"[A-Za-z’']*\d[A-Za-z’'\d]*")


# 词频阈值。用 wordfreq 而不是 /usr/share/dict/words——后者是 1934 年的美式原形
# 词表，屈折形式、英式拼写、laptop/paperwork/o'clock 这些全查不到，拿它当判据会把
# 上百条好例句误判成错字扔掉。wordfreq 的 zipf 值 2.5 上下正好分开真词和 OCR 错字：
# paperwork 3.8 / colours 4.2 / o'clock 4.0 都在上面，tme 2.0 / stuf 2.0 / therr 1.4 在下面
ZIPF_MIN = 2.5
EXTRA = {"sth", "sb", "etc"}          # 词典体例用的缩写，正文里不会出现


def isword(w):
    """这个词拼得对吗——按英语语料的词频判，不查静态词表。"""
    w = w.lower().strip("’'").replace("’", "'")
    if w in EXTRA or len(w) < 2:
        return True
    if zipf_frequency(w, "en") >= ZIPF_MIN:
        return True
    # 撇号丢了的缩写（dont）、比较级（fonder）、不常见的屈折形式（honked、denting）
    # 语料里频率都偏低，还原成原形再查一次，别把它们当错字
    # 缩写还原后的词干要求比屈折形式高（zipf 3.5）：`Ican't` 剥掉 n't 剩 `ica`，
    # 而 ica 在语料里有 2.87，按 2.5 的门槛会被当成真词放过，`Ican't` 就不拆了
    base = re.sub(r"n't$|'(ll|ve|re|d|s|m)$", "", w)
    if base != w and len(base) >= 3 and zipf_frequency(base, "en") >= 3.5:
        return True
    stems = set()
    for suf, adds in (("ies", "y"), ("es", "e"), ("ed", "e"), ("ing", "e"),
                      ("er", "e"), ("est", "e"), ("s", ""), ("ed", ""),
                      ("ing", ""), ("er", ""), ("est", ""), ("ly", "")):
        # 词干至少 4 个字母，否则 difer→dif、tme→tm 这种错字会被「还原」成真词
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            stem = w[:-len(suf)]
            stems.add(stem + adds)
            if stem[-1] == stem[-2]:            # dropped → drop、denting → dent
                stems.add(stem[:-1])
    return any(s != w and len(s) > 2 and zipf_frequency(s, "en") >= ZIPF_MIN
               for s in stems)


# 句中被无故大写的词（`You're Playing with fire`、`cap In hand`）。判据只认两类，
# 因为它们绝不可能是人名地名：① 虚词；② -ing/-ed/-ly 的屈折形式。
# 不能靠词频判——Ruth 4.05、Labour 4.70、Baker 4.23，跟普通词分不开
FUNC_CAP = set("""in of and or but to the a an at on for with from by as is are
    was were be been am do does did have has had not no so if then than that
    this these those there here your my his her its our their it he she they we
    you what when where who how why all any some each every more most very just
    only also still even about into over under after before while""".split())
# 不规则动词的过去式/分词没有 -ed 结尾，靠后缀认不出来（`young men Laid down`），
# 只能列。刻意不收 rose/read/bill/mark/will/may 这类同时是常见人名的
VERB_CAP = set("""laid said went gone took taken gave given came made saw seen
    got kept left felt found held heard told thought brought bought caught ran
    ate drank began broke chose drove fell flew grew knew led lost met paid
    rode sat sold sent shook shot spoke spent stood struck threw wore won wrote
    hurt built dealt meant slept swept wept became begun done had been was were
    knows goes says gets makes takes comes""".split())


# 永远要大写、且**不会兼作普通词**的。刻意不收 may / march / august / god / june /
# april，它们同时是情态动词、行进、威严、上帝、人名，一律大写会造出更多错
ALWAYS_CAP = set("""january february july september october november december
    monday tuesday wednesday thursday friday saturday sunday
    english french german spanish italian chinese japanese russian
    american british irish scottish welsh europe european america britain
    england scotland ireland wales london christmas easter""".split())
_CAPSTATS = {}


def capstats():
    """全书例句里每个词「句中大写」和「句中小写」各出现多少次。

    用来判断一个句中大写的词到底是不是专名。光看词频分不开——Ruth 4.05、
    Labour 4.70、Baker 4.23 跟普通词一样高。但语料自己会说话：job / know / price
    在全书上百处都是小写、一处大写都没有，那 `the Job` 里的大写就一定是 OCR 认错的。
    """
    if not _CAPSTATS:
        cap, low = collections.Counter(), collections.Counter()
        book = json.load(open(os.path.join(DATA, "idioms.json")))
        for h in book:
            for it in h["idioms"]:
                for m in re.finditer(r"(?<=[a-z,;] )([A-Za-z][A-Za-z']+)\b",
                                     it.get("ex_en") or ""):
                    w = m.group(1)
                    (cap if w[0].isupper() else low)[w.lower()] += 1
        _CAPSTATS.update({"cap": cap, "low": low})
    return _CAPSTATS


def midcap_error(word):
    """这个句中大写的词是不是 OCR 认错了大小写。"""
    low = word.lower()
    if low in ALWAYS_CAP:
        return False
    if low in FUNC_CAP or low in VERB_CAP:
        return True
    # -ing / -ed / -ly 的屈折形式。**词干必须也是个真词**——少了这一条，
    # Sal-ly、Ita-ly、Fr-ed 这些人名地名会被当成屈折形式压成小写
    m = re.fullmatch(r"(.{3,}?)(ing|ed|ly)", low)
    if m and zipf_frequency(low, "en") >= 3.5:
        # 词干要**常用**，不能只是「查得到」。`sally` 的词干 sal 加个 e 就是 sale，
        # 松一点就把 Sally / Italy / Fred / Ted 全压成了小写。
        # 加 e 的还原（make→making）只对 -ing/-ed 成立，-ly 不走这条
        stems = [m.group(1)] + ([m.group(1) + "e"] if m.group(2) != "ly" else [])
        if any(zipf_frequency(x, "en") >= 4.0 for x in stems):
            return True
    # 语料判据：全书别处小写出现过至少 5 次，且句中大写的次数不到小写的 15% →
    # 这是个普通词，`the Job` 里的大写是 OCR 认错的。
    # 不能要求「大写 0 次」——被认错的那些本身就在语料里，job 也有 1 次大写。
    # 比例卡在 15%：Mark（大写 2 / 小写 13）、Bill（5 / 9）这种人名兼普通词的会被放过
    st = capstats()
    return st["low"][low] >= 5 and st["cap"][low] <= st["low"][low] * 0.15


def polish_cn(t):
    """中文侧的字面收尾。所有例句（含自拟）都要过，两种来源的标点才一致。

    OCR 和模型都会漏下半角标点（`先别开枪!我想他们要投降了。`），
    夹在汉字中间时字距明显不对，一律换成全角。
    """
    for half, full in ((",", "，"), (";", "；"), ("?", "？"), ("!", "！"),
                       (":", "：")):
        t = re.sub(rf"(?<=[\u4e00-\u9fff]){re.escape(half)}", full, t)
    t = re.sub(r"[，。！？；]+$", lambda m: m.group(0)[0], t)
    # 中译必须有句末标点。自拟的那批模型偶尔忘了写，补一个句号
    return t + "。" if t and not t.endswith(("。", "！", "？", "”", "）")) else t


def lower_midcaps(t):
    """把句中被 OCR 无故大写的词压回小写（`got the Job` → `got the job`）。

    必须按词遍历，不能用一条正则：判断一个大写词是不是专名，要看它左右两边——
    - 左边那个词也大写（且不是句首）→ 专名词组的后半截，`Labour Party` 不能动
    - 右边那个词也大写 → 专名词组的前半截，`New York` 不能动
    句首的大写不带信息（任何词句首都大写），所以左边是句首时要当成没有信息。
    """
    toks = re.split(r"(\W+)", t)
    words = [i for i, w in enumerate(toks) if re.fullmatch(r"[A-Za-z][A-Za-z']*", w)]

    def at_sentence_start(n):
        return n == 0 or bool(re.search(r"[.!?][\"'’”\s]*$",
                                        "".join(toks[:words[n]])))

    for n, i in enumerate(words):
        # 句首本来就该大写，压了就成了 `. know what?`；全大写的是缩写（US、MP）
        if not toks[i][0].isupper() or toks[i].isupper() or at_sentence_start(n):
            continue
        prev = toks[words[n - 1]]
        # 左邻词在句首时它的大写本来就是强制的、不带信息——除非它是个实词
        # （`Third World countries` 里的 Third 就是证据，`The Job` 里的 The 不是）
        prev_is_name = prev[0].isupper() and not (
            at_sentence_start(n - 1) and prev.lower() in FUNC_CAP)
        nxt = toks[words[n + 1]] if n + 1 < len(words) else ""
        nxt2 = toks[words[n + 2]] if n + 2 < len(words) else ""
        # `Bank of China`：后面隔着一个 of 才是大写，也是专名词组
        nxt_is_name = (nxt[:1].isupper() and not nxt.isupper()) or (
            nxt.lower() in ("of", "for") and nxt2[:1].isupper())
        if prev_is_name or nxt_is_name:
            continue
        if midcap_error(toks[i]):
            toks[i] = toks[i].lower()
    return "".join(toks)


def polish(t):
    """所有例句（含自拟）都要过的字面收尾：标点空格、句中大小写。"""
    t = re.sub(r"(?<=[a-z])([,;])(?=[A-Za-z])", r"\1 ", t)
    t = re.sub(r"(?<=[a-z]\.)(?=[A-Z][a-z])", " ", t)
    t = lower_midcaps(t)
    # 反向：月份、星期、国名/语言这些永远要大写的被 OCR 压成了小写
    t = re.sub(r"\b([a-z][a-z]+)\b",
               lambda m: m.group(1).capitalize()
               if m.group(1) in ALWAYS_CAP else m.group(1), t)
    return re.sub(r"\s{2,}", " ", t).strip()


def respell(word):
    """把词里的形近字符还原，拼得回词典里的真词才认，否则原样返回。

    只碰本来就不是词的 token，所以 quite、Iraq 这些带 q 的真词一律不动；
    纯数字也不碰——`1950s`、`42nd` 拼不回真词，而真会错的 `80`、`200`
    跟真数字无法区分，那两种归 VERB_SLOT / DET_SLOT 按句法位置判。
    """
    if isword(word) or not re.search(r"[A-Za-z]", word):
        return word
    pos = [i for i, ch in enumerate(word.lower()) if ch in CONFUSE]
    if not pos or len(pos) > 4:
        return word
    cands = [list(word)]
    for i in pos:
        alts = CONFUSE[word[i].lower()]
        alts = [alts] if isinstance(alts, str) else alts
        cands = [c[:i] + [a] + c[i + 1:] for c in cands for a in alts]
    for c in cands:
        s = "".join(c)
        if isword(s):
            # 保住原来的大小写形态：L0ok → Look，不能变成 look
            return s.upper() if word.isupper() else s
    return word


def clean_en(t):
    t = t.strip(" •◆◇*·-—")
    # 音标残片先删：它里面全是 b3:、3rii 这种字母数字混搭，留着后面全判成脏词
    t = IPA_FRAG.sub(lambda m: " " if IPA_SIGN.search(m.group(0)) else m.group(0), t)
    t = re.sub(r"^[/1l|]\s+(?=[a-z])", "I ", t)         # 句首的 I 被认成 / 1 l |
    t = re.sub(r"^([/1|])(?=[a-z'])", "I", t)
    # I 和后面的词粘成一个 token：`1know we haven't` `speaking1 think`。
    # 只在剩下那半截是真词时才拆，免得动了 1950s、42nd
    t = re.sub(r"\b1(?=[a-z])([a-z']+)\b",
               lambda m: "I " + m.group(1) if isword(m.group(1)) else m.group(0), t)
    t = re.sub(r"([a-z]{3,})1\b(?= [a-z])", r"\1. I", t)
    # 大写 I 被认成 T / r / 1，撇号又常丢掉，缩写就烂成 Tve、Tll、rl、rve
    t = re.sub(r"\b[T1Ir]'?1[lI]\b", "I'll", t)          # T1l r1l 11l I'1l → I'll
    t = re.sub(r"\b[Tr]'?d\b", "I'd", t)                 # Td rd r'd → I'd
    t = re.sub(r"\b[Tr]'?(ve|re|ll|l|m)\b",
               lambda m: "I'" + ("ll" if m.group(1) == "l" else m.group(1)), t)
    t = re.sub(r"\bT\b", "I", t)
    # 撇号丢掉的缩写：youll → you'll。**必须先看整个词本身是不是常用词**——
    # were = we+re、well = we+ll、hell = he+ll，少了这道护栏会把 were 改成 we're
    # （全书 449 处）、Hell's teeth 改成 He'll's teeth。这里只留一条规则，
    # 别再另起一条忘了加护栏
    t = re.sub(r"\b(You|you|We|we|They|they|He|he|She|she|It|it|That|that|"
               r"There|there|What|what|Who|who)(ll|ve|re)\b",
               lambda m: m.group(0) if zipf_frequency(m.group(0).lower(), "en") >= 4
               else f"{m.group(1)}'{m.group(2)}", t)
    t = re.sub(r"\b([Ii])f\s*[1iI]\b", r"\1f I", t)      # ifi / if1 / IfI → if I
    # 代词 I 跟后面的词粘成一个 token：`Ihad`、`Iusually`、`Ifyou`。
    # 拆的条件有两个，缺一不可：剩下半截是真词，且**整个 token 本身不是真词**——
    # 少了后一条，Ideal 会被拆成「I deal」、Icon 拆成「I con」、Island 拆成「I sland」
    def unglue(m):
        head, tail = m.group(1), m.group(2)
        if isword(m.group(0)) or not isword(tail) or len(tail) < 2:
            return m.group(0)
        return f"{head} {tail}"

    t = re.sub(r"\b(I)([a-z][a-z']+)\b", unglue, t)
    t = re.sub(r"\bIt(is|was|has|will)\b", r"It \1", t)
    # well / hell / shell 有时是 we'll / he'll / she'll 掉了撇号。上面那条按词频
    # 放行的护栏在这儿会误放（well、hell 本身都是常用词），只能看后面跟的是什么：
    # 跟着助动词或频度副词就一定是缩写（`so today well be trying`、`hell never set`）
    t = re.sub(r"\b([Ww])ell (?=(be|have|been|never|always|soon|just|probably|"
               r"only|still|then|also|certainly)\b)", r"\1e'll ", t)
    t = re.sub(r"\b([Hh])ell (?=(be|have|been|never|always|soon|just|probably|"
               r"only|still|then|also|certainly)\b)", r"\1e'll ", t)
    t = re.sub(r"\b(He|She|That|It|There|What)s\b(?=\s+[a-z])", r"\1's", t)
    t = re.sub(r"^I (?=(you|he|she|they|we|it)\b)", "If ", t)   # `I you lay a finger`
    t = re.sub(r"\b([Ii]f)([a-z]+)\b",
               lambda m: f"{m.group(1)} {m.group(2)}"
               if m.group(2) in AFTER_IF else m.group(0), t)
    t = re.sub(r"\bE(?=\s?\d)", "£", t)                  # £500 的镑号被认成 E
    t = re.sub(r"[A-Za-z’'|0-9]+", lambda m: respell(m.group(0)), t)
    t = re.sub(r"\b(did|does|do|is|was|were|had|has|have|could|would|should|"
               r"wo|ca|ai|are)n['’](?![a-z])", r"\1n't", t)     # didn' → didn't
    # 撇号被认成了空格：`we ll just have to` → `we'll just have to`。
    # 只收 ll / ve / nt——单独成词的 ll、ve、nt 在英文里根本不存在，拼回去一定对。
    # **别把 re 也加进来**：`were` 被 OCR 断成 `we re` 的情况比真缩写多得多。
    # 后面那个 (?!['’]) 是防 `Hell's` 被断成 `He ll's` 后又拼成 `He'll's`
    t = re.sub(r"\b([a-z]+) (ll|ve|nt)(?![’'])\b", r"\1'\2", t)
    t = VERB_SLOT.sub(lambda m: m.group(1) + m.group(2) + "go", t)
    t = DET_SLOT.sub(lambda m: re.sub(r"\d+", lambda d: DET_FIX.get(d.group(0),
                                                                    d.group(0)), m.group(0)), t)
    # 孤立的 1 就是大写 I：`1 suppose`、`before 1 go to bed`。
    # 前后挂着数字、货币号、百分号的不动，那才是真的 1
    t = re.sub(r"(?<![\w.,$£€%-])1(?![\w.,%-])(?=\s+[a-z])", "I", t)
    t = re.sub(r"\bIm\b", "I'm", t)
    t = re.sub(r"\bIl\b", "I'll", t)
    # 句中大写的 Ill 是 I'll 掉了撇号（`Take a pew and Ill get us a drink`），
    # 不是形容词 ill——那个不会大写
    t = re.sub(r"(?<=[a-z] )\bIll\b(?=\s+[a-z])", "I'll", t)
    t = re.sub(r"\bIve\b", "I've", t)
    t = re.sub(r"\bdont\b", "don't", t)
    t = re.sub(r"\bcant\b", "can't", t)
    # 大小写乱掉的词（`WaS`、`tHe`）整个转小写；首字母大写和全大写的不动
    def case(m):
        w = m.group(0)
        if w in (w.lower(), w.capitalize(), w.upper()):
            return w
        # 缩写的复数（MPs、TVs、PCs）既不是 capitalize 也不是 upper，
        # 少了这一条会被压成 mps、tvs
        if len(w) > 2 and w[:-1].isupper() and w.endswith("s"):
            return w
        return w.lower()

    t = re.sub(r"\b[A-Za-z]{2,}\b", case, t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    return polish(re.sub(r"\s+", " ", t).strip())


def clean_cn(t):
    t = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", t)
    t = t.replace(",", "，").replace(";", "；").replace("?", "？")
    t = re.sub(r"[。．]{2,}", "。", t)
    # 句末标点后面粘着的零碎是下一个义项的编号/括号/重音符号被抽进来了
    # （`他击球出界。 2 (`、`我们在罗马的第一天去游览了名胜。 ˈ`），一律切掉
    t = re.sub(r"([。！？])[^\u4e00-\u9fff]{1,10}$", r"\1", t)
    t = re.sub(r"[\s•◆ˈˌ()（）0-9]+$", "", t)
    t = re.sub(r"[，。；]+$", "。", t)
    return polish_cn(re.sub(r"\s+", " ", t).strip(" ·•*"))


def usable(en, cn, idiom):
    """够不够格用作例句：完整句、中译完整、且真的用上了这条习语。"""
    if len(en.split()) < 4 or not CJK.search(cn):
        return False
    # 中译长度必须跟英文对得上。原书的中译经常跨行，而抽取时只抓到了头一个字
    # （`…it was like apples and oranges.` 的中译只剩一个「他」），
    # 这种残缺宁可整条弃用、退回自拟例句，也不能印到书上
    if len(CJK.findall(cn)) < max(4, len(en.split()) * 0.45):
        return False
    # 光看字数不够。`信不信由你，我刚在比赛中赢得` 有 13 个字，字数判据放行了，
    # 但它明显断在半句上。中译必须以句末标点收尾，全书 171 条靠这一条捞出来
    if not cn.rstrip().endswith(("。", "！", "？", "”", "）")):
        return False
    # 太长的排不进两行。PDF 里每格最多两行，例句列一行约 78 个半角宽，
    # 超过这个量只能把字号压到 4pt 以下，还不如换成自拟的那句短例句
    if sum(2 if ord(c) > 0x2e80 else 1 for c in en + cn) > 170:
        return False
    if not en[0].isupper():
        return False
    if not en.rstrip().endswith((".", "!", "?", "'", "\u201d")):
        # 没有句末标点才算截断；`How about Ruth? Have you heard from her?`
        # 是完整的两句，不能因为末词是 her 就判成半句
        return False if TRUNC.search(en.rstrip()) else False
    # 只拒绝汉字和混进来的重音符号；破折号、弯引号、重音字母都是正常英文排版。
    # CJK 标点也要拦——`It's lucky for you that 「m still awake` 里那个 「
    # 不在汉字区间里，光查 CJK 放得过去
    if CJK.search(en) or re.search(r"[ˈˌ\u3000-\u303f\uff00-\uffef]", en):
        return False
    # 英文释义被切进了例句（`The very close to sth offices are…`）。释义里才会用
    # sth / sb 这种词典占位词，真例句不会有，拿它当信号很准
    if re.search(r"\b(sth|sb|sb's|sth's)\b", en):
        return False
    # 兜底：修完还带着字母数字混搭的（`Who's duty O7 today?`、`You can't g0do`），
    # 说明这句已经被 OCR 毁到猜不回来了，整条弃用、退回自拟例句。
    # 这一条是「书上不许出现 g00dy 这种字」的最后保险，别删
    if any(not NUMERIC.match(w) for w in HASDIGIT.findall(en)):
        return False
    # 名词位上还杵着数字的（`She 248 was fortunate`、`the event of 140 your death`），
    # 是 OCR 把页码之类的东西塞进了句子，猜不回来，同样整条弃用
    if DET_SLOT.search(en):
        return False
    # 最后一道：句子里还有拼不出来的小写词（`tme`、`picrures`、`brulliantly`），
    # 就是 OCR 认错了字母而上面的规则没救回来。宁可整条弃用、退回自拟例句，
    # 也不能把错字印到书上。只查小写词——大写的多半是人名地名，词典本来就没有
    words = re.findall(r"\b[A-Za-z][A-Za-z’']*\b", en)
    if any(w[0].islower() and not isword(w) for w in words):
        return False
    return uses_idiom(en, idiom)


def uses_idiom(en, idiom):
    """例句里到底有没有用上这条习语。

    单独抽出来是因为 07_render 也要用：那边改挂条目、纠正关键词之后，行号对应的
    条目文本会变，10 这一步按旧文本判过的「用上了」可能已经不成立
    （`run aˈmok` 配到的却是 `The crowd through the city streets…`）。
    """
    # 重音符号必须先去掉再切词：`run aˈmok` 里的 amok 会被 ˈ 切成 a + mok，
    # 两截都短于 4 字符，core 落空就变成「无条件判过」，坏例句全漏过去了
    bare = re.sub(r"\([^)]*\)", "", idiom).replace("ˈ", "").replace("ˌ", "")
    # 三字母的实词也得算进来。只收 4 字母以上的话，`catch sb's ˈeye`、
    # `hold/keep sb/sth at ˈbay`、`blow your ˈtop` 的关键名词全被滤掉，
    # 只剩下动词，而例句里的动词多半是不规则变化（caught / kept / blew），比不上
    core = [w for w in re.findall(r"[a-z]{3,}", bare.lower())
            if w not in PLACEHOLDER]
    low = en.lower()
    # 按词干比，例句里的习语常有屈折变化（`take ˈaim` → `taking aim`、
    # `lose your ˈlife` → `lost their lives`、`ˌwine and ˈdine` → `wining and dining`）
    if not core:
        return True
    # 屈折变化：`lose your ˈlife` → `lost their lives`、`ˌwine and ˈdine` →
    # `wining and dining`。不规则的那批靠 07_render 里的 IRREG 表，
    # 光比词干比不出 lose / lost
    words = set(re.findall(r"[a-z']+", low))
    for w in core:
        if w[:max(3, len(w) - 2)] in low:
            return True
        if words & IRREG.get(w, set()):
            return True
    return False


def main():
    book = json.load(open(os.path.join(DATA, "idioms.json")))
    out, kept, total = {}, 0, 0
    idx = 0
    for h in book:
        for it in h["idioms"]:
            key = str(idx)
            idx += 1
            en, cn = clean_en(it["ex_en"]), clean_cn(it["ex_cn"])
            if not en:
                continue
            total += 1
            if usable(en, cn, it["idiom"]):
                out[key] = {"en": en, "cn": cn}
                kept += 1
    json.dump(out, open(os.path.join(DATA, "examples.json"), "w"),
              ensure_ascii=False, indent=0)
    print(f"抽到原书例句 {total} 条，清理后可用 {kept} 条（{kept/max(total,1):.0%}）")
    for k in list(out)[:5]:
        print(f"   {out[k]['en'][:66]}")
        print(f"   {out[k]['cn'][:40]}")


if __name__ == "__main__":
    main()
