"""Pass 08: 成品自查。把已经踩过的坑逐条查一遍，跑到数字收敛为止。

查的是**渲染成品的每一个格子**——直接调 `07_render.iter_rows()`，不再自己抄
一份取数逻辑。以前两边各写各的，渲染改了口径自查还按老口径查，
报出来的数字是假的。

每一条判据都对应一个真实犯过的错：

- 搭配其实是例句    `n accepting the award work`（原文 `In accepting the award...`）
- 搭配里有坏词      `it wil work`（wil 是 will 掉了个 l，词频却有 3.28）
- 搭配混组类型标记  `admission rates /ERB + ADMISSION app for seek`
- 搭配夹数字/怪符号 `g0od time`、`adapt to idmż 2 change a thing tx4i`
- 解释里混英文      没摘干净的隔壁栏搭配
- 例句不完整        缺主语、没有句末标点
- 例句加粗不全      `an appropriate time` 只标了 time

前几类由 `09_clean.py` 在渲染时挡掉，这里复查确认真的挡住了；
后面几条清洗管不了，只能报数。

Usage: 08_audit.py [-v]
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, mod):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, name))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


p07 = _load("07_render.py", "p07")
p09 = _load("09_clean.py", "p09")
CJK = re.compile(r"[\u4e00-\u9fff]")


def close(a, b):
    """两个词是不是同一个词的两种拼法：改一个字母、增删一个字母、
    或者相邻两个字母调个位（fibre/fiber）。"""
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    if len(a) == len(b):
        d = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        return len(d) <= 1 or (len(d) == 2 and d[1] == d[0] + 1
                               and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]])
    if abs(len(a) - len(b)) == 1:
        s, t = (a, b) if len(a) < len(b) else (b, a)
        return any(s == t[:i] + t[i + 1:] for i in range(len(t)))
    return False


def bad_gloss(cn):
    """解释格坏在哪儿，好的返回空串。**每一条都是用户点名过的**：

        向一踢              「一」是省略号被认成汉字，读出来不是人话
        对⋯踢；违抗⋯(       括号没闭合
        在⋯上的一吻！        解释里加感叹号
        …；(这个城市需要好好鞭策一下   例句译文卷进了解释格

    判据跟 `09_clean.clean_gloss` 共用（这里只查，不修），
    所以自查报的 0 是真的 0，不是自己查自己。
    """
    if re.search(r"[A-Za-z]{2,}", cn):
        return "混英文"
    if re.search(r"[A-Za-z0-9|｜~～*#$］［【】「」_]", cn):
        return "残留碎字"
    if " " in cn:
        return "夹空格"
    if (cn.count("(") + cn.count("（")) != (cn.count(")") + cn.count("）")):
        return "括号不配对"
    if "⋯" in cn:
        return "省略号变体"
    if re.search(r"[！!？?：:]", cn):
        return "怪标点"
    if cn[0] in "；，、。·-—)）" or cn[-1] in "；，、。·-—(（":
        return "首尾标点"
    for x in p09.GLOSS_SEP.split(cn):
        x = x.strip(" ·-—")
        if not x:
            continue
        if len(x) == 1 or not re.search(r"[\u4e00-\u9fff]", x):
            return f"碎渣义项 {x}"
        if len(x) > 15 or p09.SENT_ITEM.search(x):
            return f"混进句子 {x[:16]}"
        # 逐条查，不看整格：整格里别处有省略号不能给这一条背书
        if p09.LONE_YI.search(x) and "…" not in x:
            return f"省略号认成一 {x}"
        if x != p09.drop_orphan_paren(x):
            return f"括号不配对 {x}"
    return ""


def check(rows):
    bad = {k: [] for k in (
        "词头坏", "搭配坏格子", "解释空", "解释坏", "例句坏",
        "例句加粗不全")}
    for word, pos, full, cn, en, zh in rows:
        if p09.bad_head(word):
            bad["词头坏"].append(word)
        for f in full:
            why = p09.bad_phrase(f)
            if why:
                bad["搭配坏格子"].append(f"{f}  ←{why}")
        # 空白单元格也是错——不许拿留空糊弄过去
        if not cn:
            bad["解释空"].append(full[0])
        else:
            why = bad_gloss(cn)
            if why:
                bad["解释坏"].append(f"{cn[:40]}  ←{why}")
        if not en:
            continue
        plain = re.sub(r"</?b>", "", en)
        want = p09.content_words(full[0])
        why = p09.bad_sentence(plain, want)
        if why:
            bad["例句坏"].append(f"{plain[:44]}  ←{why}")
            continue
        # 加粗只查**句子里真有的那些词**。句子里压根没有的词标不上是分组问题，
        # 不是加粗的毛病，混在一起数永远收敛不了
        marked = p07.bold_words(plain, full)
        hit = " ".join(re.findall(r"<b>(.*?)</b>", marked))
        there = [w for w in want if p09.hits(w, plain)]
        miss = [w for w in there if not p09.hits(w, hit)]
        # 误报：例句里两种拼法一起写（`a grey area and a gray area`、
        # `armour/armor`、`fibre-optic/fiber-optic`），标住了一处，
        # 另一处当然标不上。跟已标住的词差一步之内的，算同一个词
        marked_words = re.findall(r"[A-Za-z]+", hit)
        miss = [w for w in miss if not any(close(w, h) for h in marked_words)]
        if miss:
            bad["例句加粗不全"].append(f"{full[0]} → {marked[:56]}")
    return bad


def main():
    book, cache = p07.load()
    done, todo = [], []
    for word, pos, full, cn, en, zh, ok, _key in p07.iter_rows(book, cache):
        (done if ok else todo).append((word, pos, full, cn, en, zh))
    raw = sum(1 for h in book for s in h["senses"] for g in s["groups"]
              for x in (g.get("subs") or []) if x.get("full"))
    kept = len(done) + len(todo)
    print(f"抽出 {raw} 行，印出 {kept} 行，清洗丢掉 {raw - kept} 行"
          f"（{(raw - kept) / raw:.1%}）")
    total = 0
    for label, part in (("已校对", done), ("未校对", todo)):
        bad = check(part)
        n = sum(len(v) for v in bad.values())
        total += n
        print(f"\n【{label}】{len(part)} 行，问题 {n} 处"
              f"（{n / max(len(part), 1):.3f} 处/行）")
        for name, items in bad.items():
            if not items:
                continue
            print(f"  {name}: {len(items)}")
            for x in items[:(10 if "-v" in sys.argv else 3)]:
                print(f"      {x}")
    print(f"\n合计 {total} 处")


if __name__ == "__main__":
    main()
