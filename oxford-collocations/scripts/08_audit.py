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


def check(rows):
    bad = {k: [] for k in (
        "词头坏", "搭配坏格子", "解释混英文", "解释残留碎字", "例句混中文",
        "例句不完整", "例句缺搭配词", "例句加粗不全")}
    for word, pos, full, cn, en, zh in rows:
        if p09.bad_head(word):
            bad["词头坏"].append(word)
        for f in full:
            why = p09.bad_phrase(f)
            if why:
                bad["搭配坏格子"].append(f"{f}  ←{why}")
        if cn:
            # 清洗过后中文列不该再有成串英文
            if re.search(r"[A-Za-z]{2,}", cn):
                bad["解释混英文"].append(cn[:40])
            # 也不该剩下孤立的拉丁字母、竖线这些 OCR 碎渣
            elif re.search(r"[A-Za-z0-9|｜~～*#$]", cn):
                bad["解释残留碎字"].append(cn[:40])
        if not en:
            continue
        plain = re.sub(r"</?b>", "", en)
        if CJK.search(plain):
            bad["例句混中文"].append(plain[:50])
        if not plain.rstrip().endswith((".", "!", "?", "'", '"', "’", "”")) \
                or len(plain.split()) < 5 or not plain[:1].isupper():
            bad["例句不完整"].append(plain[:50])
            continue
        # 例句得真的在讲这条搭配：搭配里的实词至少要出现一个
        want = p09.content_words(full[0])
        if want and not any(p09.hits(w, plain) for w in want):
            bad["例句缺搭配词"].append(f"{full[0]} → {plain[:44]}")
            continue
        # 加粗只查**句子里真有的那些词**。句子里压根没有的词标不上是分组问题，
        # 不是加粗的毛病，混在一起数永远收敛不了
        marked = p07.bold_words(plain, full)
        hit = " ".join(re.findall(r"<b>(.*?)</b>", marked))
        there = [w for w in want if p09.hits(w, plain)]
        miss = [w for w in there if not p09.hits(w, hit)]
        if miss:
            bad["例句加粗不全"].append(f"{full[0]} → {marked[:56]}")
    return bad


def main():
    book, cache = p07.load()
    done, todo = [], []
    for word, pos, full, cn, en, zh, ok in p07.iter_rows(book, cache):
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
