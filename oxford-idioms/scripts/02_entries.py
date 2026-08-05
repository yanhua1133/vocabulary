"""Pass 02: 从 data/ocr/*.json 抽出词条骨架 → data/entries.json + out/词条清单.md。

原书是双栏，每栏自上而下三类行：
- **关键词**（headword）：字号明显比正文大，OCR 行高 h 也跟着变大，这是最可靠的判据
  （光看有没有音标不行，`aback`、`betide` 这类关键词就没标音标）。
- **习语条目**：与正文同字号但加粗，OCR 拿不到字重；改用原书惯例——习语条目都标主重音
  `ˈ`（OCR 成 ASCII 单引号，且总是紧贴在某个单词前面），加上「整行没有汉字、位于栏首」。
- **交叉引用**：以 `•` 开头，指向别处的词条，不是条目本身。

Usage: 02_entries.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "data", "ocr")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")
FIRST_PDF_PAGE, FIRST_BOOK_PAGE = 18, 1      # PDF 第 18 页印着书内页码 1
LAST_PDF_PAGE = 621

HEAD_H = 0.015                               # 关键词行高阈值（正文英文行约 0.0117）
CJK = re.compile(r"[\u4e00-\u9fff]")
ACCENT = re.compile(r"(?:^|[\s(/])'[a-zA-Z]")   # 重音撇号：前面是行首/空格/括号/斜杠
# 关键词是单个词（可带连字符/撇号），后面可跟一段音标
# 结尾那根斜杠常被 OCR 吃掉（`travel /ˈtrævl/` → `travel/travl`），所以设成可选，
# 但只有斜杠齐全时才敢无视字号直接认作关键词
HEAD_RE = re.compile(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.'\-]{0,22})\s*(?:/([^/]{1,40})(/)?)?\s*$")
# 交叉引用行：`• easy → (as) easy as ABC`。项目符号和箭头 OCR 得五花八门
# （• 认成 o/+/空，→ 认成 -/+/空），但有个躲不掉的特征：箭头前的那个词一定会在
# 后半句里再出现一次（`hedge → hedge your bets`）。
# `→` 认成 `>` 时后面常常不留空格（`high >smell/stink to high heaven`），
# 但 `-` 后面必须要有空格，否则 `old-fashioned…` 这种会被误当成交叉引用
XREF_ARROW = re.compile(r"^[o•●◆*◇+]?\s*[\w'/]+\s*(?:[→>]\s*|[-—+]\s)")


def is_xref(t):
    if XREF_ARROW.match(t):
        return True
    tok = t.lower().split()
    if len(tok) < 3:
        return False
    # 只认「紧挨着重复」：`hedge hedge your bets`、`woe -woe betide sb`。
    # 放宽成「首词在后文任意位置重复」会误杀 `the ˈbigger… the ˈbetter`、
    # `for ˌbetter or (for) ˈworse`、`do better to do sth` 这些真条目。
    if tok[1][0] in "-—→>+":                 # `gravy -the gravy train`
        return True
    return tok[1].lstrip("-—→>+") == tok[0]


# 一条释义/例句的结尾：中文句号、右引号、英文句点等
END = ("。", "．", "」", "”", "\"", ".", "！", "？", "!", "?", "…")
TAGS = ("informal", "formal", "spoken", "saying", "written", "literary", "humorous",
        "disapproving", "approving", "figurative", "slang", "taboo", "old-fashioned",
        "old use", "BrE", "AmE", "especially")


def normalize(t):
    """收拾 OCR 的中文优先模式留下的痕迹。

    - 全角括号/引号还原成半角（英文条目里本来就是半角）
    - 原书用 ˈ 标主重音，Vision 认成 ASCII 的 `'`（`be'yond` → `beˈyond`）；
      但 `don't` `I'll` 这类真撇号要留着。
    - 次重音 ˌ 被认成逗号，无法与英文正文里的逗号区分（两者都是「逗号 + 空格」），
      所以**不还原**——硬还原会把 `respect, etc.` 变成 `respectˌetc.`，
      再被含重音符号的判据当成条目，误召回一大堆正文行。
    """
    t = (t.replace("（", "(").replace("）", ")").replace("，", ",")
          .replace("：", ":").replace("；", ";").replace("　", " ")
          .replace("？", "?").replace("！", "!"))
    t = re.sub(r"^[.·•\s]+", "", t)          # 行首的项目符号
    t = re.sub(r"^,\s*(?=[a-zA-Z])", "ˌ", t)  # 行首逗号其实是次重音（`，tread`）
    # 重音符号有时被认成双引号（`"life`），行内只有这一个引号时才敢还原
    if t.count('"') == 1:
        t = re.sub(r'(^|[\s(/).,])"(?=[a-zA-Z])', r"\1ˈ", t)
    t = re.sub(r"(^|[\s(/).,])'(?=[a-zA-Z])", r"\1ˈ", t)
    t = re.sub(r"(?<=[a-zA-Z])'(?!(?:t|ll|s|re|ve|d|m)\b)(?=[a-zA-Z])", "ˈ", t)
    return re.sub(r"\s+", " ", t).strip()


def finalize(t):
    """条目文本的收尾清理。只对已经判定是条目的行做，不影响判据。

    - 次重音 ˌ：还原「逗号后面不留空格」的那种（`a,stiff` → `a ˌstiff`）。
      真逗号后面一定有空格（`old-fashioned, BrE`），所以这条很安全。
    - 重音号两侧丢空格（`tradeˈsecret`、`sb'sˈheels`）：只有当拼起来不是一个词、
      而拆开的两半都是常用词时才补空格，`aˈback`、`beˈlieve` 这种词内重音要留着。
    - 括号没配平就补上右括号。
    """
    t = re.sub(r"(?<=[a-zA-Z]),(?=[a-zA-Z])", " ˌ", t)
    t = re.sub(r"([,.])(?=ˈ)", r"\1 ", t)     # `etc.ˈpath` / `carefully,ˈwarily`

    def space(m):
        a, b = m.group(1), m.group(2)
        if zipf(a + b) >= 2.0 or zipf(b) < 2.0:
            return m.group(0)
        return f"{a} ˈ{b}"

    t = re.sub(r"([a-zA-Z']+)ˈ([a-zA-Z]+)", space, t)
    t += ")" * max(0, t.count("(") - t.count(")"))
    return re.sub(r"\s+", " ", t).strip()


CONFUSE = {"i": "l", "l": "i", "s": "g", "g": "s", "c": "e", "e": "c",
           "a": "o", "o": "a", "u": "v", "v": "u", "0": "o", "1": "l", "5": "s"}


def fix_word(w):
    """关键词的 OCR 错字纠正：`iuck`→`luck`、`sood`→`good`、`CUstomer`→`customer`。

    先试小写形式，再试单字符的形近替换，取词频最高的那个；都不认识就保持原样。
    """
    if len(w) < 3:
        return w
    if w.isupper():                          # 真缩写（ABC、AWOL）保持大写，
        return w if zipf(w) < 3.0 else w.lower()   # COP/COW 这种是 OCR 大写化
    if zipf(w) >= 2.0:                       # zipf() 本身不区分大小写
        return w.lower()
    best, score = w, zipf(w)
    low = w.lower()
    for i, ch in enumerate(low):
        if ch not in CONFUSE:
            continue
        cand = low[:i] + CONFUSE[ch] + low[i + 1:]
        if zipf(cand) > score:
            best, score = cand, zipf(cand)
    return best


def zipf(w):
    from wordfreq import zipf_frequency
    return zipf_frequency(w.replace("'", "").lower(), "en")


def columns(page):
    """按栏切开：左栏 x<0.5，右栏 x>=0.5，各自按 y 从上到下。

    页眉（书眉词 + 页码）也是大字号，不排掉会被当成关键词，还会凭空多出一堆重复。
    """
    body = [l for l in page["lines"] if l["y"] > 0.055]
    left = [l for l in body if l["x"] < 0.5]
    right = [l for l in body if l["x"] >= 0.5]
    return [merge_rows(sorted(c, key=lambda l: l["y"])) for c in (left, right)]


def merge_rows(col, tol=0.006):
    """把同一行被切碎的几块拼回去。

    Vision 经常把一行吐成好几段（`used` / `when you` / `are emphasizing that sth is`），
    彼此 y 只差千分之几；不合并的话按 y 排序会把语序彻底打乱，正文就没法用了。
    """
    out = []
    for line in col:
        row = out[-1] if out else None
        # 同一行的碎片必须横向排开、互不重叠；只看 y 会把上下两行也并到一起，
        # 关键词行首当其冲（大字号的 y 偏移大），一并就整条词条丢了
        # 大字号且本身就是个「词 + 音标」的片段，一定是关键词，绝不并进上一行
        solo = line["h"] >= HEAD_H and HEAD_RE.match(line["t"].strip())
        if (row and not solo and line["y"] - row["y"] < tol
                and line["x"] >= row["_right"] - 0.01):
            row["_frag"].append((line["x"], line["t"]))
            row["_right"] = max(row["_right"], line["x"] + line["w"])
            row["h"] = max(row["h"], line["h"])
            row["x"] = min(row["x"], line["x"])
            continue
        out.append(dict(line, _frag=[(line["x"], line["t"])],
                        _right=line["x"] + line["w"]))
    for row in out:
        row["t"] = " ".join(t for _, t in sorted(row.pop("_frag")))
        row.pop("_right")
    return out


def is_headword(line, t, col_x0):
    """关键词行：顶格的单个词，后面通常跟音标。

    只靠字号不行——Vision 给的行高逐页漂移，末页 `yore /jɔː(r)/` 的 h 只有 0.0147，
    跟同页正文一样高，卡 0.015 会整页漏掉关键词。带音标的一律认，没音标的才看字号。
    """
    if CJK.search(t) or line["x"] > col_x0 + 0.03:
        return False
    if re.fullmatch(r"([A-Za-z])\1", t, re.I):   # `Aa` `Bb` 是字母分节标题
        return False
    m = HEAD_RE.match(t)
    return bool(m) and (bool(m.group(3)) or line["h"] >= HEAD_H)


def is_idiom(line, t, col_x0, prev):
    """习语条目行：整行英文、顶格，且**紧接在上一条的结尾之后**。

    字重判据行不通（Vision 的行 bbox 不够准，笔画宽度量出来粗体反而更细），
    但版面规律很硬：条目行只会出现在关键词之后、或上一条释义/例句收尾之后。
    """
    if CJK.search(t) or line["x"] > col_x0 + 0.02 or not 2 < len(t) <= 70:
        return False
    if is_xref(t):
        return False
    # 以逗号收尾且括号还没配平的，是标签写不下换了行
    # （`ahead of/behind the ˈcurve (especially AmE,`），要留给后面的合并逻辑
    if t.endswith((",", ";", ":")) and t.count("(") <= t.count(")"):
        return False
    if re.search(r"\b(ORIGIN|NOTE|OPP|SEE|SYN)\b", t) or "(=" in t:
        return False                         # 说明框标题、词源框里的释义
    if re.match(r"^\d", t):                  # 「1 used when asking...」是义项编号
        return False
    if re.match(r"^[（(][^）)]{1,18}[）)]$", t):  # 只剩 (saying) 这种标签的续行
        return False
    if t.count('"') >= 2 or re.search(r"[.?!]['\"”’]", t):  # 成对引号 = 例句
        return False
    if re.search(r"[a-z][.?!] +[A-Z]", t):   # 句中断句 = 例句
        return False
    if re.fullmatch(r"[A-Z]{3,}", t):        # NOTE / OPP 这类小标题
        return False
    if (re.match(r"^[A-Z]", t) and len(t) > 30
            and re.search(r"\b(is|are|was|were|means|refers)\b", t)):
        return False                         # NOTE 里的说明句
    if "ˈ" in t:                             # 标了主重音就是条目，与上下文无关
        return True
    if prev is None:                         # 栏首：无法判断上下文
        return False
    if not (prev == "head" or prev.rstrip().endswith(END)):
        return False
    # 没有重音符号的条目（`be about to do sth`）短而干净；释义折行则长、且多以
    # 连词/关系词起头，靠这两条把「上一条正好以句号收尾」造成的误判挡掉
    # 只挡连词/关系词打头的折行。别把 the / it / you 之类也挡掉——
    # `the curtain comes down on sth`、`you can bet…` 都是正经条目
    return len(t) <= 48 and not re.match(
        r"^(that|which|who|whom|whose|and|but|because|while|than|"
        r"used|especially|usually|often|sometimes|permission)\b", t, re.I)


def parse_page(page):
    out = []
    for col_i, col in enumerate(columns(page)):
        if not col:
            continue
        col_x0 = min(l["x"] for l in col)
        prev = None
        i = 0
        while i < len(col):
            line = col[i]
            t = normalize(line["t"])
            i += 1
            if len(t) < 2:
                continue
            if is_headword(line, t, col_x0):
                m = HEAD_RE.match(t)
                w = fix_word(m.group(1).strip())
                out.append({"kind": "head", "word": w,
                            "ipa": (m.group(2) or "").strip(), "col": col_i})
                prev = "head"
                continue
            if is_idiom(line, t, col_x0, prev):
                # 条目常被排版断成两行，断点就在括号里
                # （`against your better judgement (especially` + `ˈjudgment)`），
                # 括号没配平就把后面一两行接上来，别让续行单独成条
                stop = i + 2
                # 括号没配平、或行尾是断词连字符，都说明这一条还没写完
                while (t.count("(") > t.count(")") or t.endswith(("-", ","))) \
                        and i < len(col) and i < stop:
                    nxt = normalize(col[i]["t"])
                    # 别把关键词行或释义（带中文）吞进来：Vision 偶尔把大字号关键词
                    # 的 y 算得比它下面的条目行还大，排序后就插在中间
                    # 括号里塞不下的只会是短标签；接到一长串小写英文说明括号是
                    # OCR 弄丢的（`(informaf` ），再接下去就会把释义整段吞进来
                    if (CJK.search(nxt) or is_headword(col[i], nxt, col_x0)
                            or (len(nxt) > 35 and nxt[:1].islower())):
                        break
                    t = t[:-1] + nxt if t.endswith("-") else t + " " + nxt
                    i += 1
                out.append({"kind": "idiom", "text": finalize(t), "col": col_i})
            prev = t
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    heads = []
    for n in range(FIRST_PDF_PAGE, LAST_PDF_PAGE + 1):
        p = os.path.join(OCR, f"p{n:03d}.json")
        if not os.path.exists(p):
            continue
        book_page = n - FIRST_PDF_PAGE + FIRST_BOOK_PAGE
        for item in parse_page(json.load(open(p))):
            item["page"] = book_page
            if item["kind"] == "head":
                heads.append({"word": item["word"], "ipa": item["ipa"],
                              "page": book_page, "idioms": []})
            elif heads:
                heads[-1]["idioms"].append({"text": item["text"], "page": book_page})

    json.dump(heads, open(os.path.join(DATA, "entries.json"), "w"),
              ensure_ascii=False, indent=1)
    idioms = sum(len(h["idioms"]) for h in heads)

    lines = ["# 牛津习语词典 · 词条清单\n",
             f"\n关键词 {len(heads)} 个，习语条目 {idioms} 条。`p` 是书内页码。",
             "\n音标暂不列出：中文优先的 OCR 把 IPA 认得很差（`/əˈbæk/` → `/abaek/`），",
             "原样保留在 `data/entries.json` 里，等展开阶段用英文 OCR 重做。\n"]
    for h in heads:
        lines.append(f"\n## {h['word']}  <sub>p{h['page']}</sub>\n")
        for it in h["idioms"]:
            lines.append(f"- {it['text']}")
    open(os.path.join(OUT, "词条清单.md"), "w").write("\n".join(lines) + "\n")
    print(f"关键词 {len(heads)}，习语条目 {idioms}")
    print(os.path.join(OUT, "词条清单.md"))


if __name__ == "__main__":
    main()
