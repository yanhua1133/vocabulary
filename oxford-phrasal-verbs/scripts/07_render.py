"""Pass 07: 渲染 → out/牛津短语动词词典.md（五列表格）。

四列：**动词 / 短语动词 / 释义 / 例句**。

**语法模式（`v + adv` / `v + n/pron + adv`）根本不印。** 用户砍掉这一列之后
我又把它塞回短语动词格里，等于没砍——查词的人不看这个记号，
它只会把短语动词那一格搅乱。`data/rows.json` 里还留着，要用再说。

一行 = 一个义项。多个例句在格内换行。例句里把这条短语动词加粗。

Usage: 07_render.py
"""
import importlib.util
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")

_spec = importlib.util.spec_from_file_location(
    "p09", os.path.join(HERE, "09_clean.py"))
_p09 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p09)
bold_ex = _p09.bold_ex          # 加粗和「标不粗就丢例句」的判据都住在 09

CJK = re.compile(r"[\u4e00-\u9fff]")


def pv_lines(pv):
    """短语动词格：**分号处折行，分号本身删掉**。

    一条词条常写好几个变体（`ˌwrite sb/sth ˈin; ˌwrite sb/sth ˈinto sth`），
    原书用分号隔开。挤在一行里既读不清、又把格子撑宽，右边留一大片白；
    竖着排一行一个变体，本来就该占那么多行。

    **只在括号外面切**：`(BrE also ˌswing ˈround, ˌswing sb/sth ˈround)` 这种
    括号里的分隔是同一个变体的说明，切开就散了。
    """
    verb = _p09.head_of_pv(pv)
    out, buf, depth = [], [], 0
    for i, ch in enumerate(pv):
        if ch in "(（":
            depth += 1
        elif ch in ")）":
            depth = max(depth - 1, 0)
        if depth == 0 and (ch in ";；" or (
                # 变体之间的分号也常被认成逗号（`ˌbail ˈout, bail ˈout of sth`）。
                # **只在逗号后面又出现一次同一个动词时才敢切**——
                # 括号外的逗号也可能是 `(BrE, informal` 少了右括号
                ch == "," and verb and re.match(
                    rf"\s*[ˈˌ]?{re.escape(verb)}\b", pv[i + 1:], re.I))):
            out.append("".join(buf).strip(" ,"))
            buf = []
            continue
        buf.append(ch)
    out.append("".join(buf).strip(" ,"))
    return [x for x in out if x]


def cell(s):
    return re.sub(r"\s+", " ", (s or "").replace("|", "／")).strip()


def esc(s):
    return cell(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def keep(text):
    """还原被 esc 掉的加粗标记。"""
    return text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")


def main():
    rows_in = json.load(open(os.path.join(DATA, "rows.json")))
    n_in = sum(len(r["senses"]) for r in rows_in)
    rows, prev = [], None
    # **清洗和自查走同一个 `iter_rows`**，不许各抄一份取数逻辑
    for word, pv, pats, tags, cn, endef, ex_list in _p09.iter_rows(rows_in):
        ex = []
        for en, zh in ex_list:
            ex.append(keep(bold_ex(esc(en), pv)) + (f"<br>{esc(zh)}" if zh else ""))
        cell_pv = "<br>".join(esc(x) for x in pv_lines(pv))
        tag = ", ".join(tags)
        if tag:
            cell_pv += f' <span class="tag">({esc(tag)})</span>'
        # **义项号一律不印**。原书的编号在这儿没有参照：清洗会丢掉同一条短语动词
        # 的部分义项，剩下一个孤零零的「1」而没有「2」，读者不知道它指什么
        gloss = esc(cn)
        if endef:
            gloss += f'<br><span class="en">{esc(endef)}</span>'
        first = word != prev
        prev = word
        rows.append((f'{esc(word)}' if first else "",
                     cell_pv, gloss, "<br>".join(ex)))
    print(f"抽出 {n_in} 个义项，清洗丢掉 {n_in - len(rows)} 个")

    os.makedirs(OUT, exist_ok=True)
    n_word = sum(1 for x in rows if x[0])
    head = ["# 牛津短语动词词典\n",
            f"\n{n_word} 个动词，{len(rows)} 个义项。"
            f"例句里加粗的是当前这条短语动词。\n",
            "\n<table>",
            "<thead><tr><th>动词</th><th>短语动词</th>"
            "<th>释义</th><th>例句</th></tr></thead>"]
    for word, pv, gloss, ex in rows:
        c1 = (f'<td class="c1 newword"><b>{word}</b></td>' if word
              else '<td class="c1 cont"></td>')
        head.append(f'<tr>{c1}<td class="c2"><b>{pv}</b></td>'
                    f'<td class="c3">{gloss}</td><td class="c4">{ex}</td></tr>')
    head.append("</table>\n")
    p = os.path.join(OUT, "牛津短语动词词典.md")
    open(p, "w").write("\n".join(head) + "\n")
    print(f"{n_word} 个动词，{len(rows)} 行")
    print(p)


if __name__ == "__main__":
    main()
