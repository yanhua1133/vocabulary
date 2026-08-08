"""Pass 16: 给没有原书例句的行切批次 → work/makeex/NNN.json，交子 agent 自拟。

原书只有 23% 的搭配带例句，其余 64826 行例句列是空的。**不许留空格子、也不许
把解释列横跨过去糊弄**——每行都得有例句，没有原书的就自己写一句。

跟习语词典同一个套路：自拟的中译后面标「（自拟）」，一眼能跟原书的分开。

批次里给 agent 的是 `{k, word, coll, cn}`：k 是回填用的键（词头 + 搭配归一化），
coll 是这一格里的全部搭配（用第一条造句就行），cn 是中文解释，用来定语义。

Usage: 16_make_ex.py [每批条数，默认 120]
"""
import importlib.util
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "work", "makeex")


def key_of(word, coll):
    """回填用的键。跟 07_render 取 cache 用的是同一套写法，别改。"""
    return word + "||" + re.sub(r"[^a-z]", "", coll.lower())


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    spec = importlib.util.spec_from_file_location(
        "p07", os.path.join(HERE, "07_render.py"))
    p07 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p07)
    book, cache = p07.load()

    items = []
    for word, pos, full, cn, en, zh, _done, key in p07.iter_rows(book, cache):
        if en.strip():
            continue
        items.append({"k": key, "word": word, "pos": pos,
                      "coll": full[:3], "cn": cn})

    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    for i in range(0, len(items), size):
        n = i // size + 1
        json.dump(items[i:i + size],
                  open(os.path.join(WORK, f"{n:04d}.json"), "w"),
                  ensure_ascii=False, indent=1)
    print(f"{len(items)} 行缺例句 → {(len(items) + size - 1) // size} 批"
          f"（每批 {size} 条）→ {WORK}")


if __name__ == "__main__":
    main()
