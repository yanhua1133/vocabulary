"""Pass 07: 渲染最终成品 → out/牛津习语词典.md。

四列：**单词 / 习语 / 中文解释 / 例句**。单词就是原书的关键词，一个单词下面的
若干条习语连排在一起，单词列只在第一行写一次。

条目文本、中文释义、例句都优先取 data/cache.json（子 agent 校对/重写过的），
没有缓存就退回 data/idioms.json 里从扫描件抽出来的原文。

Usage: 07_render.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")
# 关键词行的音标偶尔会被切成独立一行，混进条目里（`ˈa:rmtʃer; a:rmˈtʃer/`）
IPA_JUNK = re.compile(r"(;.*/|/\s*$|^[^A-Za-z]*[a-z]:)")


def cell(s):
    return (s or "").replace("|", "／").replace("\n", " ").strip()


def junk(idiom):
    return bool(IPA_JUNK.search(idiom)) and " " not in idiom.strip(" /")


def main():
    book = json.load(open(os.path.join(DATA, "idioms.json")))
    cache_path = os.path.join(DATA, "cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}

    rows, idx, filled, dropped = [], 0, 0, 0
    for h in book:
        first, seen = True, set()
        for it in h["idioms"]:
            rec = cache.get(str(idx))
            idx += 1
            # 同一个单词下同一条习语被抽到两次（跨栏、跨页续行造成的），只留一条。
            # 去重放在渲染这一步做，不动 data/idioms.json 的序号——缓存是按序号存的
            key = re.sub(r"[^a-z]", "", (rec["i"] if rec else it["idiom"]).lower())
            if not key or key in seen or junk(rec["i"] if rec else it["idiom"]):
                dropped += 1
                continue
            seen.add(key)
            if rec:
                filled += 1
                idiom, cn = rec["i"], rec["cn"]
                en_ex, _, cn_ex = rec["e"].partition("  ")
            else:
                idiom, cn = it["idiom"], it["cn"]
                en_ex, cn_ex = it["ex_en"], it["ex_cn"]
            ex = f"{cell(en_ex)}<br>{cell(cn_ex)}" if cn_ex else cell(en_ex)
            rows.append((cell(h["word"]) if first else "", cell(idiom),
                         cell(cn), ex))
            first = False

    os.makedirs(OUT, exist_ok=True)
    lines = ["# 牛津习语词典\n",
             f"\n{sum(1 for r in rows if r[0])} 个单词，{len(rows)} 条习语。"
             f"其中 {filled} 条（{filled/max(len(rows),1):.1%}）的释义和例句经过校对重写。\n",
             "\n<table>",
             "<thead><tr><th>单词</th><th>习语</th><th>中文解释</th>"
             "<th>例句</th></tr></thead>"]
    for word, idiom, cn, ex in rows:
        w = f"<b>{word}</b>" if word else ""
        lines.append(f"<tr><td>{w}</td><td>{idiom}</td>"
                     f"<td>{cn}</td><td>{ex}</td></tr>")
    lines.append("</table>\n")
    p = os.path.join(OUT, "牛津习语词典.md")
    open(p, "w").write("\n".join(lines))
    print(f"{len(rows)} 行，其中 {filled} 行用了校对后的内容；"
          f"去掉重复/音标残片 {dropped} 条")
    print(p)


if __name__ == "__main__":
    main()
