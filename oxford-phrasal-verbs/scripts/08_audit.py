"""Pass 08: 成品自查。查的是**渲染成品的每一个格子**，不是中间数据。

判据全部住在 `09_clean.py`（`bad_pv` / `bad_cn` / `bad_en` / `bad_sentence`），
这里只负责调用和统计。**自查和清洗必须是同一个函数**——两边各写一份的话，
渲染改了口径自查还按老口径查，报出来的 0 是假的（搭配词典上栽过）。

查四列，每条判据都对应一个真实看到的错：

| 列 | 长什么样 |
|---|---|
| 短语动词 | `sb's beˈhalf`（条目被腰斩）、`aˈgree to sth` 里的 gree 被当坏词 |
| 中文释义 | `因压力身体或精神饼溃`（形近字）、括号不配对、混英文 |
| 英文释义 | `to lose a game VeT) badly`（反白标签串进来）、`to A 1 to believe`、`}为` |
| 例句 | 英文不完整、译文缺失、加粗没标上 |

Usage: 08_audit.py [-v]
"""
import collections
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")


def _load(name, mod):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, name))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


p07 = _load("07_render.py", "p07")
p09 = _load("09_clean.py", "p09")


def check():
    rows = json.load(open(os.path.join(DATA, "rows.json")))
    bad = collections.defaultdict(list)
    n = 0
    for row in p09.iter_rows(rows):
        word, pv, pats, tags, cn, en, ex = row
        # 短语动词必须含它的词头动词——这是内容一致性的第一道关
        if p09.head_of_pv(pv) and word.lower()[:max(3, len(word) - 2)] \
                not in p09.plain_pv(pv).lower():
            bad["词头对不上"].append(f"[{word}] {pv[:44]}")
        n += 1
        why = p09.bad_tag(tags)
        if why:
            bad["语域标签坏"].append(f"{pv} ({tags})  ←{why}")
        why = p09.bad_pv(pv)
        if why:
            bad["短语动词坏"].append(f"{pv}  ←{why}")
        why = p09.bad_cn(cn)
        if why:
            bad["中文释义坏"].append(f"{cn[:40]}  ←{why}")
        why = p09.bad_en(en)
        if why:
            bad["英文释义坏"].append(f"{en[:52]}  ←{why}")
        if not cn:
            bad["没有中文释义"].append(pv)
        for a, b in ex:
            why = p09.bad_sentence(a, p09.content_words(p09.plain_pv(pv)))
            if why:
                bad["例句坏"].append(f"{a[:48]}  ←{why}")
            elif not b:
                bad["例句没中译"].append(a[:48])
            elif p09.bad_zh(b):
                bad["例句中译坏"].append(f"{b[:40]}  ←{p09.bad_zh(b)}")
            elif "<b>" not in p07.bold_ex(a, pv):
                # 渲染层已经把标不上的例句整条丢了，这儿再查一遍确认真丢干净
                bad["例句没标粗"].append(f"{pv} → {a[:44]}")
    return n, bad


def main():
    n, bad = check()
    total = sum(len(v) for v in bad.values())
    print(f"印出 {n} 行，问题 {total} 处（{total / max(n, 1):.3f} 处/行）")
    for name, items in sorted(bad.items(), key=lambda kv: -len(kv[1])):
        print(f"  {name}: {len(items)}")
        for x in items[:(12 if "-v" in sys.argv else 4)]:
            print(f"      {x}")


if __name__ == "__main__":
    main()
