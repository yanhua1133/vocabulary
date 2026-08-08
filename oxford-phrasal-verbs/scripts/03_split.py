"""Pass 03: 把 data/entries.json 里的「条目块」拆成字段 → data/rows.json。

一个条目块是一整段挤在一起的原文：

    ˌmuster sth ˈup to find the courage, strength, etc. that you need in order
    to do sth difficult or unpleasant 鼓起(勇气、劲头等);振作起来:She could barely
    muster up the strength to get out of bed. 她几乎连起床的力气都没有了。

要拆成：短语动词 / 语域标签 / 义项号 / 英文释义 / 中文释义 / 例句(英+中)。
版式很规整，四条边界都有硬特征：

1. **条目 → 释义**：释义的开头就那么几种（`to …`、`used …`、`if …`、`(of …)`、
   `1 …`、名词条目的 `n a …`）。找**最后一个重音符号之后**的第一个开头词，
   不能从头找——`ˌbreathe ˈin` 的 `in` 后面也可能跟 `to sth`。
2. **英文释义 → 中文释义**：第一个汉字。
3. **中文释义 → 例句**：冒号后面紧跟大写英文。原书就是这个体例。
4. **例句之间**：`◇`。这个符号最常被 OCR 认成中文句号，也认成 `o` / `0` / `O`
   （搭配词典上同一个坑），所以判据写成「汉字 + 分隔符 + 大写英文」。

Usage: 03_split.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

CJK = re.compile(r"[\u4e00-\u9fff]")
# 释义的开头。`to` 最常见；名词条目是 `n a/an/the …`；`(of …)` 是主语限制
# **`to` 要区分不定式和小品词**：`add ˈon to sth` 里的 to 是小品词、还属于条目，
# `to build an extra room` 里的 to 才是释义的开头。判据是后面跟的是宾语占位符
# 还是动词——少了这条，`add ˈon; ˌadd ˈon to sth` 会在 `to sth` 处腰斩
DEF_START = re.compile(
    r"(?:^|\s)(?=(?:to(?!\s+(?:sth|sb|it|yourself|each|one another|doing)\b)"
    r"|used|if|when|usually|always|not|a|an|the|"
    r"\(of\b|\(used\b|\(especially\b|\[\+|\d(?:\s|$))(?:\s|$|\b))")
# 语域标签：紧跟在条目后面的括号（`(AmE)`、`(BrE, informal)`、`(formal)`）
TAG_WORDS = ("informal", "formal", "spoken", "written", "literary", "humorous",
             "disapproving", "approving", "figurative", "slang", "taboo",
             "old-fashioned", "rare", "less frequent", "BrE", "AmE", "AustralE",
             "CanE", "IrishE", "ScotE", "SAfrE", "NAmE", "especially")
# 混在正文里的反白标签：`IDM`、`SYN`、`OPP`、`NOTE`、`note at …`。
# 行首的那些 02 已经摘走了，这里管的是**挤在同一段中间**的
INLINE_LABEL = re.compile(
    r"\s*(?:[A-Z]{2,5}\]?|Io?M|DPR|EY?A?N|BwN|BXN|oB[J]?\]?|o8J|os\]?)\s+"
    r"(?=[a-zA-Z(])|(?:\s*[o0O]?\s*note at [A-Z][A-Z\s]+)")
# 义项号：汉字或句末标点之后的一个数字，后面接释义开头
# 义项号：汉字或句末标点之后、**或者整段开头**的一个数字，后面接释义开头。
# 少了「整段开头」这一支，`ˌcook sth ˈup 1 to cook sth…2 (informal) to invent…`
# 的第一个义项号切不掉，`1 to cook sth` 会原样印进英文释义
SENSE = re.compile(r"(?:(?<=[\u4e00-\u9fff。;])|^)\s*(\d)\s+"
                   r"(?=to\b|used\b|if\b|\(|when\b)")
# 例句引导符 ◇。OCR 认成句号 / o / 0 / O / 〇 / 圆点都有——`〇` 是汉字零，
# 少认这一个变体，`阳光从窗户倾泻而入。〇Fans were still…` 就切不开
# 引导符前面除了汉字和句末标点，还可能是省略号（`可是…◇He just barged…`），
# 不认这一种的话两句例句会粘成一句
EX_SEP = re.compile(r"(?<=[\u4e00-\u9fff。!?…])\s*[。．.•·◇○〇oO0◊]\s*(?=[A-Z\"'I])")
# 中文释义和例句之间的冒号
EX_COLON = re.compile(r"[:：]\s*(?=[A-Z\"'I])")


# 标签括号里出现的连接词，本身不是标签但要跟着一起吃掉
TAG_GLUE = {"also", "and", "or", "more", "less", "much", "esp", "usually",
            "sometimes", "often", "used", "in", "the", "a", "an", "not"}


def strip_tags(t):
    """摘掉条目后面的语域标签，返回 (剩下的文本, 标签列表)。

    扫描件常把右括号吃掉（`(BrE, informal` 收不了尾）。
    **不能写成「懒惰匹配到第一个空格」**——`(AmE, informal to defeat sb…`
    只会吃掉 `AmE,`，剩下的 `informal` 就原样印进英文释义里去了（804 处里的大头）。
    没有右括号时改成**逐个词往下吃，吃到第一个不是标签词为止**。
    """
    tags = []
    while True:
        m = re.match(r"\s*\(([^()]{1,60})\)", t)          # 括号齐全，整段吃掉
        if m and any(w.lower() in m.group(1).lower() for w in TAG_WORDS):
            tags.append(m.group(1).strip().rstrip(",;"))
            t = t[m.end():]
            continue
        m = re.match(r"\s*\(", t)                          # 右括号被吃掉了
        if not m:
            break
        rest, took = t[m.end():], []
        for w in re.finditer(r"\s*([A-Za-z][\w.-]*)\s*[,;/]?", rest):
            low = w.group(1).lower().rstrip(".")
            if any(low == x.lower() for x in TAG_WORDS) or low in TAG_GLUE:
                took.append((w.group(1), w.end()))
                continue
            break
        # 至少要吃到一个真标签词，不然 `(of a vehicle…` 这种主语限制会被误吃
        if not took or not any(
                any(w.lower() == x.lower() for x in TAG_WORDS) for w, _ in took):
            break
        tags.append(" ".join(w for w, _ in took))
        t = rest[took[-1][1]:]
    return t.lstrip(" ,;)"), tags


TAG_PAREN = re.compile(r"\((?=[^()]{0,40}?(?:" + "|".join(TAG_WORDS) + r")\b)",
                       re.I)


SENSE_NO = re.compile(r"\s\d\s+(?=to\b|used\b|if\b|\()")


def cut_at(raw, pos):
    """从 pos 之后找条目的终点。三种终点取最早的：释义开头、语域标签的左括号、
    义项号。**语域标签的左括号也是终点**——只看释义开头的话，收尾括号被扫描件
    吃掉时（`(AmE, informa`）里面的 `informa` 挡在前面，要一直找到后面的
    `if you blank out` 才切，整个标签被算进短语动词里。"""
    ends = [m.start() for m in (DEF_START.search(raw, pos),
                                TAG_PAREN.search(raw, pos)) if m]
    m = SENSE_NO.search(raw, pos)
    if m:
        ends.append(m.start() + 1)
    return min(ends) if ends else None


def cut_head(raw):
    """把「短语动词」从块首切下来，返回 (短语动词, 剩下的)。

    从**最后一个**重音符号往前退着试。不能直接用最后一个：`ˈtaste`、
    `SYN ˈmake up sth` 这些引用也带重音，落在整段的末尾，从那儿找释义开头
    什么也找不到，整段都会被当成短语动词（`acˈcount for sth 1 to explain… 说明…`）。
    也不能直接用第一个：变体之间还有重音（`add ˈon; ˌadd ˈon to sth`），
    用第一个会在第一个变体处腰斩。
    退到「切出来的条目不含汉字、且不长于 110 个字符」为止。
    """
    pos = [m.end() for m in re.finditer(r"[ˈˌ]", raw)] or [0]
    for p in reversed(pos):
        cut = cut_at(raw, p)
        if cut is None:
            continue
        pv = raw[:cut].strip(" ,;:")
        if not CJK.search(pv) and len(pv) <= 110:
            return pv, raw[cut:].strip()
    cut = cut_at(raw, 0)
    if cut is None:
        return raw.strip(), ""
    return raw[:cut].strip(" ,;:"), raw[cut:].strip()


def split_ex(t):
    """把「英文例句 + 中译」的串切成 [(英, 中)]。"""
    out = []
    for chunk in EX_SEP.split(t):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = CJK.search(chunk)
        if not m:
            out.append([chunk, ""])
            continue
        out.append([chunk[:m.start()].strip(), chunk[m.start():].strip()])
    return out


def split_sense(t):
    """一个义项：英文释义 / 中文释义 / 例句列表。"""
    body, _, ex = t.partition("\x00")
    parts = EX_COLON.split(t, 1)
    body, ex = (parts + [""])[:2]
    m = CJK.search(body)
    en = body[:m.start()].strip() if m else body.strip()
    cn = body[m.start():].strip() if m else ""
    return {"en": re.sub(r"\s+", " ", en).strip(" ,;:"),
            "cn": cn.strip(" ,;:"), "ex": split_ex(ex)}


def split_entry(raw):
    """一个条目块 → {pv, tags, senses:[{en, cn, ex}]}。"""
    raw = INLINE_LABEL.sub(" ", " " + raw + " ").strip()
    pv, rest = cut_head(raw)
    rest, tags = strip_tags(rest)
    # 义项号把剩下的切成几段。`1` 常常在第一段前面，切出来的头一块是空的
    pieces = SENSE.split(rest)
    senses = []
    if len(pieces) > 1:
        head = pieces[0].strip()
        if head:
            senses.append(split_sense(head))
        for num, seg in zip(pieces[1::2], pieces[2::2]):
            s = split_sense(seg.strip())
            s["no"] = num
            senses.append(s)
    else:
        senses.append(split_sense(rest))
    return {"pv": pv, "tags": tags,
            "senses": [s for s in senses if s["en"] or s["cn"]]}


def main():
    heads = json.load(open(os.path.join(DATA, "entries.json")))
    rows, n_sense, n_ex = [], 0, 0
    for h in heads:
        for e in h["entries"]:
            d = split_entry(e["raw"])
            if not d["pv"] or not d["senses"]:
                continue
            pats = " ".join(e["pats"])
            # 模式行：`◆ v + adv ◆ v + n/pron + adv`。项目符号认得五花八门，
            # 统一成 `v + adv ／ v + n/pron + adv`
            pats = [re.sub(r"\s*\+\s*", " + ", p.strip())
                    for p in re.split(r"[•◆*◇]|(?<=[a-z])\s+(?=v\s*\+)", pats)
                    if re.search(r"v\s*\+", p)]
            rows.append({"word": h["word"], "ipa": h["ipa"], "page": e["page"],
                         "pv": d["pv"], "tags": d["tags"],
                         "pats": pats, "labels": e["labels"],
                         "senses": d["senses"]})
            n_sense += len(d["senses"])
            n_ex += sum(len(s["ex"]) for s in d["senses"])
    json.dump(rows, open(os.path.join(DATA, "rows.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"短语动词 {len(rows)} 条，义项 {n_sense} 个，例句 {n_ex} 句")
    print(f"有模式的 {sum(1 for r in rows if r['pats'])}，"
          f"有中文释义的 {sum(1 for r in rows if any(s['cn'] for s in r['senses']))}")
    print(os.path.join(DATA, "rows.json"))


if __name__ == "__main__":
    main()
