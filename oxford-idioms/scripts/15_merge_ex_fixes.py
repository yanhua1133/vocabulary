"""Pass 15: 把子 agent 校对的结果并回 data/examples.json。

不无条件接受模型给的句子。每条改动都要过三道校验，任何一道不过就丢掉不改：

1. 原句必须跟 examples.json 里现存的那条**一字不差**——对不上说明批次是旧的，
   或者 agent 抄错了行，这时候写进去会改错条目。
2. 改动幅度不能太大。只许修错，不许重写：改完的句子跟原句的公共部分要占七成以上。
   `difflib` 的相似度低于 0.7 一律视为模型自己另写了一句。
3. 改完必须仍然通过 `10_clean_ex.usable()`——别把一句干净的例句改成有错字的。

第 2、3 道不过时**不是原样留下，而是整条弃用、退回自拟例句**。模型之所以要重写，
是因为原句已经烂到没法修（`It's too bad you seat!`、`Let's a new car.`——
中间整段被邻栏的内容顶掉了），留着比换成自拟的更糟。只有第 1 道不过才原样跳过，
那是批次对不上，不该动数据。

Usage: 15_merge_ex_fixes.py
"""
import difflib
import glob
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
WORK = os.path.join(ROOT, "work", "exfix")
SIMILAR = 0.7


def main():
    spec = importlib.util.spec_from_file_location(
        "p10", os.path.join(HERE, "10_clean_ex.py"))
    p10 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p10)

    path = os.path.join(DATA, "examples.json")
    ex = json.load(open(path))
    applied, dropped = 0, 0
    skipped = {"对不上原句": 0, "没有 k": 0}
    for f in sorted(glob.glob(os.path.join(WORK, "*.out.json"))):
        for it in json.load(open(f)).get("bad", []):
            k, old, new = it.get("k"), it.get("en", ""), it.get("fix", "")
            if k not in ex:
                skipped["没有 k"] += 1
                continue
            # 比对忽略大小写：批次发出去之后清理管线又调过一次「句中无故大写」的
            # 判据，`the Job` 变成了 `the job`，逐字比会白丢掉三十多条有效修正。
            # 大小写归 polish() 统一管，这里只需确认是同一句
            if ex[k]["en"].lower() != old.lower():
                skipped["对不上原句"] += 1
                continue
            fixed = p10.clean_en(new)
            if (difflib.SequenceMatcher(None, old, new).ratio() < SIMILAR
                    or not fixed
                    or not p10.usable(fixed, ex[k]["cn"], it.get("idiom", ""))):
                del ex[k]                   # 原句烂到只能重写 → 整条退回自拟
                dropped += 1
                continue
            ex[k]["en"] = fixed
            applied += 1
    json.dump(ex, open(path, "w"), ensure_ascii=False, indent=0)
    print(f"并入 {applied} 条修正，弃用 {dropped} 条（退回自拟）" +
          ("，跳过 " + "、".join(f"{k} {v}" for k, v in skipped.items() if v)
           if any(skipped.values()) else ""))
    print("下一步：07_render.py 重渲染，08_audit.py 复核")


if __name__ == "__main__":
    main()
