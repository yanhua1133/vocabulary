"""Pass 03: 把搭配组的原文拆成「搭配词 / 中文 / 例句」→ data/groups.json。

一个搭配组的原文长这样（`|` 分小类，`◇` 引出例句）：

    negotiate, work out 商议/拟定协议 ◇They are working out a formal ceasefire ~.
    他们正在商定正式停火协议。| conclude, enter into, reach, sign 达成协议；签订协议
    ◇After hours of talks the government and the union have reached an ~. 经过数小
    时的谈判，政府与工会达成了协议。

所以每个小类切出来是：**英文搭配词 → 中文释义 → ◇ → 英文例句 → 中文翻译**。

两个符号都被 OCR 认花了，得按变体收：
- 小类分隔 `|` → 认成 `l` `I` `！` `丨`（`|` 本身 39482 次，变体加起来还有 3 万多）
- 例句引导 `◇` → 认成 `•` `◎` `*`

Usage: 03_split.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

CJK = re.compile(r"[\u4e00-\u9fff]")
# 小类分隔：竖线及其 OCR 变体，后面跟着小写字母/括号/波浪号才算
SUBSEP = re.compile(r"\s*[|Il丨！]\s+(?=[a-z(~])")
# 例句：`◇` 常被认成 •◎*，但**最常见的是被并成中文句号**——中文释义后面直接
# 跟一句大写打头的英文，就是例句开始。例句吃到英文句末标点，后面紧跟的中文是它的翻译。
EXAMPLE = re.compile(
    r"(?:[•◎○●※◇]|\s\*\s|(?<=[\u4e00-\u9fff])\s*[。.;:]\s*)"
    r"\s*([A-Z(][^\u4e00-\u9fff]{10,}?[.!?])"
    # 中译必须**以句末标点收尾**，而且中间不许出现小类分隔符。
    # 原来写成 `[^A-Z]{0,80}`，会一路吃到下一个小类里去，例句后面拖着
    # `／ effectively, largely virtually 事实上终止…` 这种狗屁不通的尾巴
    r"\s*([\u4e00-\u9fff][^A-Z|Il丨！]{0,60}?[。！？])?")


def take_examples(text):
    """先把例句整段摘出去，剩下的才好按小类切——不然例句里的标点会把小类切碎。"""
    got = []

    def grab(m):
        got.append((re.sub(r"\s+", " ", m.group(1)).strip(" *"),
                    (m.group(2) or "").strip(" *·。")))
        return " ｜EX｜ "

    return EXAMPLE.sub(grab, text), got


def split_sub(part):
    """一个小类 → (搭配词, 中文释义)。"""
    part = part.replace("｜EX｜", " ").strip(" ,;.·")
    if not part:
        return None
    m = re.match(r"^([^\u4e00-\u9fff]*?)\s*([\u4e00-\u9fff].*)$", part)
    words, cn = (m.group(1), m.group(2)) if m else (part, "")
    words = re.sub(r"\s+", " ", words).strip(" ,;.·")
    cn = re.sub(r"\s+", " ", cn).strip(" ,;·")
    if not words and not cn:
        return None
    return {"words": words, "cn": cn}


def main():
    book = json.load(open(os.path.join(DATA, "book.json")))
    total = subs = with_words = with_cn = with_ex = 0
    for h in book:
        for s in h["senses"]:
            for g in s["groups"]:
                total += 1
                body, examples = take_examples(g["text"])
                out, used = [], 0
                # 例句按它在原文里的位置归属到所在的小类——占位符 ｜EX｜ 就是为此留的。
                # 整组共用一条例句的话，同一句会重复印在七八行上
                for part in SUBSEP.split(body):
                    n_ex = part.count("｜EX｜")
                    got = split_sub(part)
                    if got:
                        got["ex"] = examples[used:used + n_ex]
                        out.append(got)
                        subs += 1
                        with_words += bool(got["words"])
                        with_cn += bool(got["cn"])
                        with_ex += bool(got["ex"])
                    used += n_ex
                g["subs"] = out
                g["examples"] = examples[used:]      # 没落到任何小类里的

    json.dump(book, open(os.path.join(DATA, "groups.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"{total} 个搭配组 → {subs} 个小类")
    print(f"  有搭配词 {with_words} ({with_words/max(subs,1):.0%})，"
          f"有中文 {with_cn} ({with_cn/max(subs,1):.0%})")
    print(f"  带例句的小类 {with_ex} ({with_ex/max(subs,1):.0%})")


if __name__ == "__main__":
    main()
