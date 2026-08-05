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
HEAD_RE = re.compile(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.'\-]{0,22})\s*(?:/([^/]{1,40})/)?\s*$")
# 交叉引用行：`• easy → (as) easy as ABC`。项目符号和箭头 OCR 得五花八门
# （• 认成 o/+/空，→ 认成 -/+/空），但有个躲不掉的特征：箭头前的那个词一定会在
# 后半句里再出现一次（`hedge → hedge your bets`）。
XREF_ARROW = re.compile(r"^[o•●◆*◇+]?\s*[\w'/]+\s*[-—→>+]\s")


def is_xref(t):
    if XREF_ARROW.match(t):
        return True
    tok = t.lower().split()
    if len(tok) < 3:
        return False
    # 只认「紧挨着重复」：`hedge hedge your bets`、`woe -woe betide sb`。
    # 放宽成「首词在后文任意位置重复」会误杀 `the ˈbigger… the ˈbetter`、
    # `for ˌbetter or (for) ˈworse`、`do better to do sth` 这些真条目。
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
    t = re.sub(r"^[,.·•\s]+", "", t)         # 行首残留的次重音符号/项目符号
    # 重音符号有时被认成双引号（`"life`），行内只有这一个引号时才敢还原
    if t.count('"') == 1:
        t = re.sub(r'(^|[\s(/])"(?=[a-zA-Z])', r"\1ˈ", t)
    t = re.sub(r"(^|[\s(/)])'(?=[a-zA-Z])", r"\1ˈ", t)
    t = re.sub(r"(?<=[a-zA-Z])'(?!(?:t|ll|s|re|ve|d|m)\b)(?=[a-zA-Z])", "ˈ", t)
    return re.sub(r"\s+", " ", t).strip()


def columns(page):
    """按栏切开：左栏 x<0.5，右栏 x>=0.5，各自按 y 从上到下。

    页眉（书眉词 + 页码）也是大字号，不排掉会被当成关键词，还会凭空多出一堆重复。
    """
    body = [l for l in page["lines"] if l["y"] > 0.055]
    left = [l for l in body if l["x"] < 0.5]
    right = [l for l in body if l["x"] >= 0.5]
    return [sorted(c, key=lambda l: l["y"]) for c in (left, right)]


def is_headword(line, t, col_x0):
    """关键词行：顶格的单个词，后面通常跟音标。

    只靠字号不行——Vision 给的行高逐页漂移，末页 `yore /jɔː(r)/` 的 h 只有 0.0147，
    跟同页正文一样高，卡 0.015 会整页漏掉关键词。带音标的一律认，没音标的才看字号。
    """
    if CJK.search(t) or line["x"] > col_x0 + 0.03:
        return False
    m = HEAD_RE.match(t)
    return bool(m) and (bool(m.group(2)) or line["h"] >= HEAD_H)


def is_idiom(line, t, col_x0, prev):
    """习语条目行：整行英文、顶格，且**紧接在上一条的结尾之后**。

    字重判据行不通（Vision 的行 bbox 不够准，笔画宽度量出来粗体反而更细），
    但版面规律很硬：条目行只会出现在关键词之后、或上一条释义/例句收尾之后。
    """
    if CJK.search(t) or line["x"] > col_x0 + 0.02 or not 2 < len(t) <= 70:
        return False
    if is_xref(t):
        return False
    if t.endswith((",", ";", ":", "-")):     # 半句，肯定是正文折行
        return False
    if re.match(r"^\d", t):                  # 「1 used when asking...」是义项编号
        return False
    if re.match(r"^[（(][^）)]{1,18}[）)]$", t):  # 只剩 (saying) 这种标签的续行
        return False
    if t.count('"') >= 2 or re.search(r"[.?!]['\"”]", t):   # 成对引号 = 例句
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
    return len(t) <= 48 and not re.match(
        r"^(that|which|who|whom|whose|and|but|or|so|because|when|while|if|"
        r"than|then|there|here|this|these|those|it|they|he|she|you|we|"
        r"used|especially|usually|often|sometimes|permission|the)\b", t, re.I)


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
                w = m.group(1).strip()
                if len(w) > 2 and w[0].isupper() and w[1:].islower():
                    w = w.lower()            # OCR 常把词首字母认成大写
                out.append({"kind": "head", "word": w,
                            "ipa": (m.group(2) or "").strip(), "col": col_i})
                prev = "head"
                continue
            if is_idiom(line, t, col_x0, prev):
                # 条目常被排版断成两行，断点就在括号里
                # （`against your better judgement (especially` + `ˈjudgment)`），
                # 括号没配平就把后面一两行接上来，别让续行单独成条
                stop = i + 2
                while t.count("(") > t.count(")") and i < len(col) and i < stop:
                    nxt = normalize(col[i]["t"])
                    # 别把关键词行或释义（带中文）吞进来：Vision 偶尔把大字号关键词
                    # 的 y 算得比它下面的条目行还大，排序后就插在中间
                    if CJK.search(nxt) or is_headword(col[i], nxt, col_x0):
                        break
                    t += " " + nxt
                    i += 1
                out.append({"kind": "idiom", "text": t, "col": col_i})
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
