"""Pass 02: 从 data/ocr/*.json 抽出词条骨架 → data/book.json。

原书是双栏，每栏自上而下四类行，靠「顶格 + 行首长相」就能分开：

    ability noun                      ← 词头：小写词 + 词性
    1 skill/power to do sth 能力       ← 义项：数字打头
    ADJ. considerable, enormous …      ← 搭配组：全大写标签打头
      续行一律缩进，跟着上一块走

比习语词典好认得多——那本要靠重音符号和上下文猜，这本每类行的行首都有硬特征。

Usage: 02_entries.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "data", "ocr")
DATA = os.path.join(ROOT, "data")
FIRST_PDF_PAGE, FIRST_BOOK_PAGE, LAST_PDF_PAGE = 27, 1, 2050

CJK = re.compile(r"[\u4e00-\u9fff]")
# 词性：原书印的是 noun / verb / adj. / adv. 这几种
# OCR 常把 adj. 认成 ad. / ady. / adi.，把 adv. 认成 adr.，一并认掉
# 长的写在前面！正则交替是最左优先，`ad` 排在 `adv`/`adj` 前面会先吃掉前缀、
# 再卡在后面的字母上整个匹配失败，形容词词头会漏掉九成
POS = (r"(?:nouns|noun|verbs|verb|advs|adv|adverb|adjs|adj|adjective|"
       r"ady|adi|adr|ad|preps|prep|conj|pron|det|number)\.?(?=\s|$)")
# 末尾别再加 \b：POS 里的 `\.?` 会把那个点吃掉，`adj.` 之后是句点+行尾，
# 构不成单词边界，加了 \b 会让所有带点的词性（adj. adv. prep.）全部匹配失败
HEAD_RE = re.compile(rf"^([A-Za-z][A-Za-z'\- ]{{0,28}}?)\s+{POS}", re.I)
SENSE_RE = re.compile(r"^(\d{1,2})\s+(.{2,})")
HEAD_ONLY = re.compile(rf"^[A-Za-z][A-Za-z'\- ]{{0,28}}?\s+{POS}\s*$", re.I)
# 搭配组标签：ADJ. / ADV. / VERB + NOUN / NOUN + VERB / PREP. / PHRASES / QUANT. …
# 大小写放宽，OCR 常把 ADV. 认成 ADv.；靠下面那张词表兜底，不会误收普通句子。
# 标签和后面的搭配词之间**不一定有空格**（OCR 出来常是 `ADJ.draft`），
# 所以点后面的空格要可选——少了这条，那一整组会被并进义项文本里。
GROUP_RE = re.compile(r"^([A-Z][A-Za-z]*(?:\s*\+\s*[A-Za-z]+)*)\.?\s*(?=[a-z(~\[])")
# 别把 NUMBER 放进来：例句里换行开头的 number 会被当成组标签，
# 还会把真正的那一组从中间腰斩（核对时抓到 12 处）
GROUP_WORDS = {"ADJ", "ADV", "VERB", "NOUN", "PREP", "PHRASES", "QUANT",
               "PHRASE", "PRON", "DET", "CONJ"}
# 搭配词典不会拿虚词当词头。`the number` 这种是把正文里的
# `the number of…` 误认了，认下来会把邻近词条的搭配全领走
NOT_HEAD = {"the", "a", "an", "of", "in", "on", "at", "to", "and", "or",
            "but", "that", "this", "it", "is", "are", "be", "as", "for",
            "with", "by", "from", "not", "no", "so", "if", "than", "then"}


def normalize(t):
    t = (t.replace("（", "(").replace("）", ")").replace("，", ",")
          .replace("：", ":").replace("；", ";").replace("　", " ")
          .replace("｜", "|").replace("Ⅰ", "|").replace("１", "1"))
    # 组内小类的分隔符原书是 |，OCR 认成 I/l/丨/！ 的时候居多
    # 分隔符 `|` 还被认成 」』〕 这些右括号类字形
    t = re.sub(r"(?<=[\u4e00-\u9fff\s])[Il丨|！」』〕]\s*(?=[a-z(~])", " | ", t)
    # 代替词头的 `~` 常被认成汉字「一」，夹在英文中间时还原回去——
    # 不还原的话例句里凭空多个汉字，按「例句里不含汉字」找边界就断了
    t = re.sub(r"(?<=[a-zA-Z ])一(?=[\s.,;:)])", "~", t)
    t = re.sub(r"(?<=[a-zA-Z])\s*一\s*(?=[a-zA-Z])", " ~ ", t)
    return re.sub(r"\s+", " ", t).strip()


def dehyphen(t):
    """抹掉原书换行处的断词连字符：`Trad- itional` → `Traditional`、
    `nat– ural` → `natural`、`punish– ment` → `punishment`。

    得在**跨行拼接之后**做——断词的两半本来就在两行上，normalize 只看得见单行。
    连字符后面带空格才算断词，`slash-and-burn` 这种真连字符没有空格。
    """
    return re.sub(r"(?<=[a-zA-Z])[-–—]\s+(?=[a-z])", "", t)


def merge_rows(col, tol=0.006):
    """把被切碎的同一行拼回去：碎片必须横向排开、互不重叠。

    词头片段绝不并进上一行——`ablaze ad.` 被并到 abhorrent 的 VERBS 行中间后，
    词头位置就串了，后面 ability 的十几条搭配全挂到了 ablaze 名下。
    """
    out = []
    for line in col:
        row = out[-1] if out else None
        solo = bool(HEAD_RE.match(line["t"].strip())) and line["h"] >= 0.014
        # 词头行两头都要挡住：既不能并进上一行，也不能把后面的碎片吸进来。
        # 少了后半条，`ablaze adj.` 会把 ability 的 ADJ 续行吞掉，
        # 于是 ablaze 跑到 ability 前面、把人家十几条搭配全领走了
        if (row and not solo and not row.get("_solo")
                and line["y"] - row["y"] < tol
                and line["x"] >= row["_right"] - 0.01):
            row["_frag"].append((line["x"], line["t"]))
            row["_right"] = max(row["_right"], line["x"] + line["w"])
            row["h"] = max(row["h"], line["h"])
            continue
        out.append(dict(line, _frag=[(line["x"], line["t"])],
                        _right=line["x"] + line["w"], _solo=solo))
    for row in out:
        row["t"] = " ".join(t for _, t in sorted(row.pop("_frag")))
        row.pop("_right")
        row.pop("_solo", None)
    return out


def columns(page):
    """双栏切开，去掉页眉页脚。"""
    body = [l for l in page["lines"] if 0.045 < l["y"] < 0.965]
    return [merge_rows(sorted((l for l in body if lo <= l["x"] < hi),
                              key=lambda l: l["y"]))
            for lo, hi in ((0.0, 0.49), (0.49, 1.0))]


def kind_of(t, x, col_x0, fill=False):
    """判断这一行是什么。只有顶格的行才可能开新块，缩进的都是续行。

    `fill=True` 的行是 03_gapfill 补回来的，只当续行使——补行难免有乱码
    （`ablaze adj. * đ „*x c` 就是补出来的，还落在了右栏中间），
    让它开新词条会把后面十几条搭配全带偏。
    """
    if x > col_x0 + 0.012:
        return None
    m = GROUP_RE.match(t)
    if m:
        head = m.group(1).upper().replace(".", "").split("+")[0].strip()
        if head in GROUP_WORDS:
            tag = re.sub(r"\s*\+\s*", " + ", m.group(1).upper().rstrip("."))
            return ("group", tag, t[m.end():])
    m = SENSE_RE.match(t)
    if m:
        return ("sense", m.group(1), m.group(2))
    m = HEAD_RE.match(t)
    # 看第一个词就够：`of a` 这种误判也是虚词打头
    if (m and not CJK.search(m.group(0))
            and (m.group(1).strip().lower().split() or [""])[0] not in NOT_HEAD):
        # 补回来的行也可以是词头，但整行必须干干净净只有「词 + 词性」。
        # 带尾巴的多半是乱码（`ablaze adj. * đ „*x c`），认了会把后面的搭配带偏
        if fill and not HEAD_ONLY.match(t):
            return None
        return ("head", m.group(1).strip(), t[m.end(1):].strip())
    return None


POS_FIX = {"adi": "adj", "ady": "adj", "ad": "adj", "adr": "adv",
           "nouns": "noun", "verbs": "verb", "adjective": "adj",
           "adverb": "adv", "preps": "prep"}


def norm_pos(rest):
    """词性归一化：OCR 把 adj. 认成 adi./ady./ad. 的很多，统一写法。"""
    w = (rest.split() or [""])[0].strip(".").lower()
    return POS_FIX.get(w, w)


def parse_page(page):
    """返回这一页的块。页首那些还没开新块的续行用 `cont` 标出来，
    交给 main 拼回上一页的最后一块——每页各扫各的会把跨页的续尾整段丢掉。"""
    out = []
    for col in columns(page):
        if not col:
            continue
        col_x0 = min(l["x"] for l in col)
        for line in col:
            t = normalize(line["t"])
            if len(t) < 2:
                continue
            got = kind_of(t, line["x"], col_x0, line.get("fill", False))
            if got:
                out.append(list(got))
            elif out:
                out[-1][2] += " " + t          # 续行拼进上一块
            else:
                out.append(["cont", "", t])    # 页首续行，归属在上一页
    return out


def main():
    book, cur_head, cur_sense = [], None, None
    pages = 0
    for n in range(FIRST_PDF_PAGE, LAST_PDF_PAGE + 1):
        p = os.path.join(OCR, f"p{n:03d}.json")
        if not os.path.exists(p):
            continue
        pages += 1
        page_no = n - FIRST_PDF_PAGE + FIRST_BOOK_PAGE
        for kind, key, rest in parse_page(json.load(open(p))):
            if kind == "cont":                        # 上一页最后一块的续尾
                if cur_sense and cur_sense["groups"]:
                    cur_sense["groups"][-1]["text"] += " " + rest
                elif cur_sense:
                    cur_sense["text"] += " " + rest
                continue
            if kind == "head":
                cur_head = {"word": key, "pos": norm_pos(rest),
                            "page": page_no, "senses": []}
                cur_sense = None
                book.append(cur_head)
            elif kind == "sense":
                if cur_head is None:
                    continue
                cur_sense = {"n": int(key), "text": rest, "groups": []}
                cur_head["senses"].append(cur_sense)
            elif kind == "group":
                if cur_head is None:
                    continue
                if cur_sense is None:                 # 没分义项的词条
                    cur_sense = {"n": 0, "text": "", "groups": []}
                    cur_head["senses"].append(cur_sense)
                cur_sense["groups"].append({"type": key, "text": rest})

    for h in book:                                # 块都拼完了，再统一抹断词
        for sense in h["senses"]:
            sense["text"] = dehyphen(sense["text"])
            for g in sense["groups"]:
                g["text"] = dehyphen(g["text"])

    json.dump(book, open(os.path.join(DATA, "book.json"), "w"),
              ensure_ascii=False, indent=1)
    senses = sum(len(h["senses"]) for h in book)
    groups = sum(len(s["groups"]) for h in book for s in h["senses"])
    print(f"{pages} 页：词头 {len(book)}，义项 {senses}，搭配组 {groups}")


if __name__ == "__main__":
    main()
