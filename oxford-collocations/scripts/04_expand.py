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


def fix_token(w):
    """搭配词里的 OCR 错字。扫描件左边缘常把首字母吃掉，尤其是 `l`——
    `ocal`→local、`argely`→largely、`ikely`→likely、`aunch`→launch、
    `anguage`→language，全书 6911 处。也有形近认错的（`lefeat`→defeat）。

    只在原词本身不是词、且候选唯一又够常见时才改。原书是权威词典，
    「搭配疑误」几乎都是这儿丢的字母，不是书错。
    """
    from wordfreq import zipf_frequency as z

    if w in _CACHE:
        return _CACHE[w]
    low = out = w.lower()
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
        # 门槛不能卡在「查不到的词」上——`ife` 的词频有 2.69 却是 life 掉了首字母。
        # 改成：本身不常见（<3.0），且换法明显更常见（高出 1.5 个数量级）才动
        if not out.isalpha() or len(out) < 3 or base >= 3.0:
            break
        best, score = out, base + 1.5
        for c in "abcdefghijklmnopqrstuvwxyz":       # 首/尾字母被吃掉
            for cand in (c + out, out + c):
                if z(cand, "en") > score:
                    best, score = cand, z(cand, "en")
        for i in range(len(out)):                    # 形近认错
            for a, b in PAIRS:
                if out[i:i + len(a)] != a:
                    continue
                cand = out[:i] + b + out[i + len(a):]
                if z(cand, "en") > score:
                    best, score = cand, z(cand, "en")
        for i in range(len(out)):                    # 多认了一个字母
            cand = out[:i] + out[i + 1:]
            if len(cand) >= 3 and z(cand, "en") > score:
                best, score = cand, z(cand, "en")
        if best == out:
            break
        out = best
    if out != w.lower():
        out = out.capitalize() if w[0].isupper() else out
    else:
        out = w
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
        suf = m.group(1) or ""
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
    return re.sub(r"~(ing|ed|es|s|d)?", form, w)


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
                 lambda m: f"<b>{put_head('~' + (m.group(1) or ''), head)}</b>", out)
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


def main():
    book = json.load(open(os.path.join(DATA, "groups.json")))
    total = 0
    for h in book:
        head, pos = h["word"], h.get("pos", "")
        for s in h["senses"]:
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
    print(f"展开出 {total} 条完整搭配")
    for h in book[:1]:
        for s in h["senses"][:1]:
            for g in s["groups"][:2]:
                print(f"  [{g['type']}]", " / ".join(
                    w for sub in g["subs"] for w in sub["full"])[:76])


if __name__ == "__main__":
    main()
