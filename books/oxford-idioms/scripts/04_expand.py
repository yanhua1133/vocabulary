"""Pass 04: 给每条习语补上中文释义和原书例句 → data/idioms.json。

02 只切出了「关键词 + 条目」的骨架，这一步把条目下面那一段正文也切出来。
原书一条的正文长这样（英文释义在前，中文释义跟在后面，冒号之后是例句）：

    be down on your ˈluck (informal)
    have no money because of a period of bad luck 因倒霉而缺钱；
    落魄；潦倒：He looks like a man who's down on his luck.
    他看起来像个倒霉透顶的人。

所以：`：` 之前的中文 = 释义，`：` 之后的英文 = 例句，例句后面的中文 = 例句翻译。
OCR 会把一行切碎、把标点认错，全部按「行拼成一段」再切，比逐行匹配稳。

Usage: 04_expand.py
"""
import importlib.util
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
OCR = os.path.join(ROOT, "data", "ocr")
DATA = os.path.join(ROOT, "data")

spec = importlib.util.spec_from_file_location("p02", os.path.join(HERE, "02_entries.py"))
p02 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p02)

CJK = p02.CJK
COLON = "：:"


def blocks(page):
    """走一遍页面，产出 (kind, 文本, 后面跟着的正文行) 三元组。"""
    out = []
    for col in p02.columns(page):
        if not col:
            continue
        col_x0 = min(l["x"] for l in col)
        prev, i = None, 0
        while i < len(col):
            line = col[i]
            t = p02.normalize(line["t"])
            i += 1
            if len(t) < 2:
                continue
            if p02.is_headword(line, t, col_x0):
                m = p02.HEAD_RE.match(t)
                out.append(["head", p02.fix_word(m.group(1).strip()), []])
                prev = "head"
                continue
            if p02.is_idiom(line, t, col_x0, prev):
                stop = i + 2
                while (t.count("(") > t.count(")") or t.endswith(("-", ","))) \
                        and i < len(col) and i < stop:
                    nxt = p02.normalize(col[i]["t"])
                    if (CJK.search(nxt) or p02.is_headword(col[i], nxt, col_x0)
                            or (len(nxt) > 35 and nxt[:1].islower())):
                        break
                    t = t[:-1] + nxt if t.endswith("-") else t + " " + nxt
                    i += 1
                out.append(["idiom", p02.finalize(t), []])
            elif out:
                out[-1][2].append(t)         # 正文行挂到上一个条目名下
            prev = t
    return out


def split_body(lines):
    """把条目下面的正文切成 中文释义 / 英文例句 / 例句中译。"""
    text = " ".join(lines)
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)   # 行尾断词：some- thing → something
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "", "", ""

    # 中文释义：第一个冒号之前的中文（英文释义丢掉，中文的更好用）
    head = re.split(f"[{COLON}]", text, 1)
    cn = "".join(re.findall(r"[\u4e00-\u9fff。、，；；？！…—·（）()]+", head[0]))
    cn = re.sub(r"^[，、；。\s]+|[，、；\s]+$", "", cn)

    en_ex = cn_ex = ""
    if len(head) > 1:
        rest = head[1].strip()
        # 例句：一段以句号收尾的英文；后面紧跟的中文就是它的翻译
        m = re.match(r"([^\u4e00-\u9fff]{10,200}?[.!?])\s*([\u4e00-\u9fff][^A-Za-z]*)",
                     rest)
        if m:
            en_ex = re.sub(r"\s+", " ", m.group(1)).strip(" •◆◇*")
            cn_ex = m.group(2).strip()
    return cn, en_ex, cn_ex


def main():
    heads = []
    for n in range(p02.FIRST_PDF_PAGE, p02.LAST_PDF_PAGE + 1):
        p = os.path.join(OCR, f"p{n:03d}.json")
        if not os.path.exists(p):
            continue
        book_page = n - p02.FIRST_PDF_PAGE + p02.FIRST_BOOK_PAGE
        for kind, text, body in blocks(json.load(open(p))):
            if kind == "head":
                heads.append({"word": text, "page": book_page, "idioms": []})
            elif heads:
                cn, en_ex, cn_ex = split_body(body)
                heads[-1]["idioms"].append({
                    "idiom": text, "cn": cn, "page": book_page,
                    "ex_en": en_ex, "ex_cn": cn_ex})

    json.dump(heads, open(os.path.join(DATA, "idioms.json"), "w"),
              ensure_ascii=False, indent=1)
    total = sum(len(h["idioms"]) for h in heads)
    with_cn = sum(1 for h in heads for x in h["idioms"] if x["cn"])
    with_ex = sum(1 for h in heads for x in h["idioms"] if x["ex_en"])
    print(f"关键词 {len(heads)}，条目 {total}")
    print(f"  有中文释义 {with_cn} ({with_cn/total:.1%})")
    print(f"  有原书例句 {with_ex} ({with_ex/total:.1%})")


if __name__ == "__main__":
    main()
