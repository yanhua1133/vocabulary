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
                    full = [expand_one(w, head, g["type"], pos)
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
