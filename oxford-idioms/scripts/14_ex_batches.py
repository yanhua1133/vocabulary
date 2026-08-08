"""Pass 14: 把成品实际用到的原书例句切成批次 → work/exfix/NN.json，交子 agent 逐条校对。

为什么非派模型不可：`10_clean_ex.py` 能修的是**字面**错误（形近字、撇号、大小写），
但扫描件还有三类错误规则查不出来，因为改错之后每个词单独看都是对的——

- 词序错乱：`She completely was taken aback`（原书 `She was completely taken aback`）
- 英文释义被切进例句中间：`The very close to sth offices are a heartbeat away…`
- OCR 把一个词认成了另一个**真词**：`Hus pride`→`His`、`ail types`→`all`、
  `well be trying`→`we'll`

随机抽 80 条独立复核，这三类合计 10%。4100 多条里约 400 条要修，只能全量过。

批次里只放**成品真正用到的**那些例句（examples.json 里判定可用、且渲染时也确实
回填进去的），不是全部 5257 条——被弃用的那些已经换成自拟例句了，校对它们没意义。

Usage: 14_ex_batches.py [每批条数，默认 60]
"""
import importlib.util
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "work", "exfix")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    p07 = load("p07", "07_render.py")
    book, cache = p07.load()
    rows, *_ = p07.final_rows(book, cache)
    rows = [list(r) for r in rows]
    rows, _ = p07.with_book_examples(rows)
    rows, _ = p07.regroup(rows)
    rows, _ = p07.append_lost(rows)
    rows = [list(r) for r in rows]
    for r in rows:
        r[1] = p07.tidy_idiom(r[1])
    scores = p07.load_scores()
    rows = [r for r in rows
            if not p07.fragment(r[1], scores.get(re.sub(r"[^a-z]", "",
                                                        r[1].lower())))]
    # 例句在 examples.json 里的 key 就是 r[7]（条目在 idioms.json 里的流水号），
    # 回填时也按它查，所以批次里必须带上，否则改完对不回去
    items = [{"k": r[7], "idiom": r[1], "en": r[3]}
             for r in rows if len(r) > 7 and "（自拟）" not in r[4]]

    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    n = 0
    for i in range(0, len(items), size):
        n += 1
        json.dump(items[i:i + size],
                  open(os.path.join(WORK, f"{n:02d}.json"), "w"),
                  ensure_ascii=False, indent=1)
    print(f"{len(items)} 条原书例句 → {n} 批（每批 {size} 条）→ {WORK}")
    print(f"提示词见 prompts/INSTRUCTIONS_EXFIX.md，跑完用 15_merge_ex_fixes.py 并入")


if __name__ == "__main__":
    main()
