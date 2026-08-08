"""Pass 02: 从 data/ocr/*.json 抽出骨架 → data/entries.json + out/词条清单.md。

原书双栏，每栏自上而下四类行：

- **词头**（动词）：`muster /ˈmʌstə(r)/`、`bring /brɪŋ/ (brought, brought /brɔːt/)`。
  字号比正文大，但 Vision 给的行高在这本书里不可靠（`muss /mʌs/` 只有 0.0132，
  跟正文一样），**只能靠音标**：这本书的词头一律带 `/.../`。
- **短语动词条目**：`ˌmuster sth ˈup to find the courage… 鼓起… : She could barely…`。
  条目本身加粗，Vision 拿不到字重，但有两个很硬的特征：
  ① 原书用**悬挂缩进**，条目行比续行**外凸约 0.015**；
  ② 条目一律标重音（主重音 ˈ 被认成 `'`，次重音 ˌ 被认成全角逗号）。
  **释义和例句跟条目挤在同一段里**，不像习语词典那样各占一行，所以这里只切出
  「条目块」的整段原文，字段拆分留给 03_split.py。
- **标签行**：`OBJ strength, energy`、`SYN summon sth up`、`NOTE …`、`OPP …`。
  原书是反白小方块，OCR 认得五花八门（`oB`、`o时`、`EYN`、`BXN`、`WOTE`），
  只能按「行首那一小块像哪个标签」模糊匹配。
- **模式行**：`◆ v + adv ◆ v + n/pron + adv`。短语动词能不能被宾语隔开全看这行，
  是这本书最有价值的信息之一，单独抽成一列。

Usage: 02_entries.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "data", "ocr")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")
FIRST_PDF_PAGE, FIRST_BOOK_PAGE = 23, 1      # PDF 第 23 页印着书内页码 1
LAST_PDF_PAGE = 525

CJK = re.compile(r"[\u4e00-\u9fff]")
# 右栏左边界在 0.49~0.51 之间飘。**切分线不能放在 0.5**——`brim /brɪm/` 的 x
# 是 0.4928，会被划到左栏去，跟左栏的行并成一条（`ˌbreeze ˈthrough sth … brim /brɪm/`）
COL_SPLIT = 0.45
# 正文左边界约 0.088。比这更左的都是 gapfill 从整栏宽的空带里刮出来的横跨两栏的碎行
MIN_X = 0.05
# 词头：一个词（可带连字符）+ 音标 + 可选的屈折形式 `(brought, brought /brɔːt/)`。
# 两种写法：斜杠齐全的、和收尾斜杠被 OCR 吃掉的。
# **音标里绝不能有汉字**——松一点写成 `[^/]{1,40}` 的话，续行
# `sb /sth or to do sth 渴望;热盼:I was aching for/` 会被当成词头 `sb`，
# 把后面整段释义都领走，还凭空多出一个词条（假词头 1020 个）
HEAD_FULL = re.compile(r"^([A-Za-z][A-Za-z'\-]{1,20})\s*/([^/\u4e00-\u9fff]{1,44})/"
                       r"\s*(\(.{0,60})?$")
# 收尾斜杠没了就只认「不含空格的一小段」，否则半句英文都能冒充音标
HEAD_HALF = re.compile(r"^([A-Za-z][A-Za-z'\-]{1,20})\s*/([^/\u4e00-\u9fff\s]{1,24})$")


def head_of(t):
    """这一行是不是词头，返回 (词, 音标, 屈折形式) 或 None。"""
    m = HEAD_FULL.match(t) or HEAD_HALF.match(t)
    if not m:
        return None
    g = m.groups() + ("",)
    return m.group(1), m.group(2).strip(), (g[2] or "").strip()


HEAD_RE = HEAD_FULL          # merge_rows 只需要「像不像词头」这个粗判据
# 模式行：`◆ v + adv ◆ v + n/pron + adv`。项目符号认得五花八门（•◆*e），
# 但 `v +` 这个组合躲不掉
PAT_RE = re.compile(r"^[•◆*◇+eo\s]*v\s*\+", re.I)
# 反白标签。OCR 出来的样子太多，按「去掉非字母后跟哪个标签最像」认
LABELS = {"OBJ": "OBJ", "OB": "OBJ", "OBI": "OBJ", "OBJ]": "OBJ", "OS": "OBJ",
          "SYN": "SYN", "EYN": "SYN", "BYN": "SYN", "BXN": "SYN", "SYNN": "SYN",
          "EYAN": "SYN", "SY": "SYN", "SJ": "OBJ", "OSJ": "OBJ",
          "OPP": "OPP", "OPN": "OPP", "OPD": "OPP", "OP": "OPP",
          "NOTE": "NOTE", "WOTE": "NOTE", "MOTE": "NOTE", "NOTF": "NOTE"}
LABEL_HEAD = re.compile(r"^([A-Za-z\]）)]{2,5})\s+(?=[A-Za-z\u4e00-\u9fff*])")


def normalize(t):
    """收拾中文优先 OCR 留下的痕迹。跟习语词典同一套，区别是这本书的
    次重音 ˌ 被认成**全角**逗号（`，muscle ˈup`），先换成半角再统一处理。"""
    t = (t.replace("（", "(").replace("）", ")").replace("，", ",")
          .replace("：", ":").replace("；", ";").replace("　", " ")
          .replace("？", "?").replace("！", "!").replace("⋯", "…"))
    t = re.sub(r"^[.·•\s]+", "", t)
    t = re.sub(r"^,\s*(?=[a-zA-Z])", "ˌ", t)          # 行首逗号是次重音
    t = re.sub(r"(?<=[;:(\s])\s*,\s*(?=[a-zA-Z])", " ˌ", t)   # `ˈup;,muscle sth`
    if t.count('"') == 1:
        t = re.sub(r'(^|[\s(/).,;])"(?=[a-zA-Z])', r"\1ˈ", t)
    t = re.sub(r"(^|[\s(/).,;])'(?=[a-zA-Z])", r"\1ˈ", t)
    t = re.sub(r"(?<=[a-zA-Z])'(?!(?:t|ll|s|re|ve|d|m)\b)(?=[a-zA-Z])", "ˈ", t)
    return re.sub(r"\s+", " ", t).strip()


def columns(page):
    """按栏切开。页眉（书眉词 + 页码）在 y<0.055，不排掉会被当成词头。"""
    body = [l for l in page["lines"] if l["y"] > 0.055 and l["x"] > MIN_X]
    out = []
    for c in ([l for l in body if l["x"] < COL_SPLIT],
              [l for l in body if l["x"] >= COL_SPLIT]):
        out.append(merge_rows(c, col_x0(c)) if c else [])
    return out


def col_x0(col):
    """栏的左边界。取 15% 分位，不取最小值——一个异常靠左的碎行就能把基线拽偏，
    整栏的条目行都会被当成续行丢掉（搭配词典上栽过，1673 个词头集体消失）。"""
    xs = sorted(l["x"] for l in col)
    return xs[max(0, int(len(xs) * 0.15) - 1)]


def merge_rows(col, x0, tol=0.006):
    """把同一行被 Vision 切碎的几块拼回去（`ˌmuster sth` + `ˈup` + `to find…`）。

    **先按 y 聚成条带，带内再按 x 排序**，不能一路按 y 顺序往上一行贴：
    `ˌmuster sth`(x=0.497) 的 y 比 `ˈup`(x=0.618) 还大千分之一，按 y 排就变成
    `ˈup …` 自己一行、`ˌmuster sth` 另一行，一条目被劈成两条，
    `ˈup to find the courage` 那半截还会被当成新条目。

    三个保护，每条都对应真犯过的错：
    - 碎片必须横向排开、互不重叠；
    - **顶格的碎片一定是新行的开头**（一行里只有第一块能顶格），
      少了这条 `brighten sth ˈup …` 会跟 `brighten ˈup 1 …` 并成一条；
    - 词头片段绝不并进上一行——判据得在 `normalize` 之后做，
      原始文本里的全角括号（`bring /brɪŋ/（brought…`）会让词头正则匹配不上。
    """
    bands, cur = [], []
    for line in sorted(col, key=lambda l: l["y"]):
        if cur and line["y"] - cur[0]["y"] < tol:
            cur.append(line)
        else:
            cur = [line]
            bands.append(cur)
    out = []
    for band in bands:
        for line in sorted(band, key=lambda l: l["x"]):
            row = out[-1] if out else None
            solo = (bool(HEAD_RE.match(normalize(line["t"])))
                    or line["x"] <= x0 + 0.010)
            if (row and not solo and row["_band"] is band
                    and line["x"] >= row["_right"] - 0.01):
                row["_frag"].append((line["x"], line["t"]))
                row["_right"] = max(row["_right"], line["x"] + line["w"])
                row["h"] = max(row["h"], line["h"])
                continue
            out.append(dict(line, _frag=[(line["x"], line["t"])],
                            _band=band, _right=line["x"] + line["w"]))
    for row in out:
        row["t"] = " ".join(t for _, t in sorted(row.pop("_frag")))
        row.pop("_right")
        row.pop("_band")
    return dedupe(out)


def dedupe(col):
    """扔掉 gapfill 重复补出来的行。

    `03_gapfill` 把疑似空带整条裁下来重 OCR，行距估歪时会把**上一行或下一行**
    再认一遍，于是成品里出现两条几乎一样的条目（`ace sb ˈout (AmE, informal) to
    defeat sb in` 一次完整一次截断）。判据：带 `fill` 标记，且它的文字是相邻
    某一行的开头（或反过来），留长的那条。
    """
    def key(s):
        return re.sub(r"[^a-z]", "", s.lower())

    drop = set()
    for i, row in enumerate(col):
        if not row.get("fill"):
            continue
        a = key(row["t"])
        # 空带里刮出来的行常把**几个不相邻的物理行**用空格拼成一条：
        #   `brighten sth ˈup to make sth more inter- brighten ˈup 1 if the weather…`
        #   `brim ˈover (with sth) (usually… brim ˈover with sth (usually… bring /brɪm/ (brought`
        # 前者把下一条的条目名顶到了上一条头上，后者一条顶三条。切不开，整条不要——
        # **Vision 自己那几行本来就在，丢掉这条一点内容不少**（核对过：
        # `brighten sth ˈup to make sth more inter.` 另有一条正常的行）
        # 重音符号要在 normalize **之后**数——原始文本里它还是 ASCII 单引号，
        # 直接数 `[ˈˌ]` 一个都数不到，这条判据等于没写
        two_heads = (len(re.findall(r"[ˈˌ]", normalize(row["t"]))) >= 2
                     and len(a) > 40)
        if len(a) < 6 or re.search(r"\S/[^/\s]{2,20}/", row["t"][8:]) or two_heads:
            drop.add(i)
            continue
        # **比的是「包含」不是「前缀」**：`brighten ˈup 1 if the weather brightens up,`
        # 整句嵌在旁边那条的中间，只比前缀查不出来
        for j in range(max(0, i - 3), min(len(col), i + 4)):
            if j == i or j in drop:
                continue
            b = key(col[j]["t"])
            if len(b) >= 6 and (b[:24] in a or a[:24] in b):
                drop.add(i if len(a) <= len(b) else j)
                break
    return [r for i, r in enumerate(col) if i not in drop]


def label_of(t):
    """行首是不是反白标签，返回规范名和剩下的正文。"""
    m = LABEL_HEAD.match(t)
    if not m:
        return None, t
    key = re.sub(r"[^A-Za-z]", "", m.group(1)).upper()
    if key in LABELS:
        return LABELS[key], t[m.end():].strip()
    return None, t


ACCENT = re.compile(r"[ˈˌ]")
CONFUSE = {"i": "l", "l": "i", "s": "g", "g": "s", "c": "e", "e": "c",
           "a": "o", "o": "a", "u": "v", "v": "u", "0": "o", "1": "l", "5": "s",
           "t": "f", "f": "t", "r": "n", "n": "r", "h": "b", "b": "h"}
# 交叉引用和正文碎片冒充词头：`OVER /…`、`sb /sth …`、`if /…`。
# 词头一定是动词，虚词和全大写的小品词标题都不是
NOT_HEAD = {"sb", "sth", "it", "if", "the", "a", "an", "and", "or", "to", "of",
            "in", "on", "up", "out", "off", "over", "down", "away", "back",
            "note", "syn", "obj", "opp", "idm", "phr"}


def zipf(w):
    from wordfreq import zipf_frequency
    return zipf_frequency(w.replace("'", "").lower(), "en")


def fix_word(w):
    """词头的 OCR 错字纠正：`borew`→brew、`oristle`→bristle、`ilter`→filter。

    词头一错整个词条就查不到，所以宁可多试几种形近替换。
    先试小写，再逐字符试形近替换，取词频最高的；都不认识就原样留着，
    交给后面的「不是真词就不要」把它丢掉。
    """
    if len(w) < 3:
        return w
    if w.isupper():
        return w if zipf(w) < 3.0 else w.lower()
    # **本来就是个词就别动它**。门槛卡 2.5 的话 `muss`(2.43) 会被「纠正」成
    # `mugs`(3.24)，`muss` 这个词头连带它的 `muss sth up` 全丢
    if zipf(w) >= 1.5:
        return w.lower()
    best, score = w.lower(), zipf(w)
    low = w.lower()
    for i, ch in enumerate(low):
        if ch not in CONFUSE:
            continue
        cand = low[:i] + CONFUSE[ch] + low[i + 1:]
        if zipf(cand) > score + 1.5:
            best, score = cand, zipf(cand)
    # 首字母被扫描件吃掉的（`ilter`→filter、`lare`→flare、`ghaw`→gnaw）
    for c in "abcdefghijklmnopqrstuvwxyz":
        if zipf(c + low) > score + 1.0:
            best, score = c + low, zipf(c + low)
    # 多认出来一个字母的（`borew`→brew、`gqun`→gun、`gUSSY`→gussy）。
    # 少了这条，`brew` 整个词条会因为词头站不住被丢掉，它的短语动词全挂到
    # 前一个词头 `breeze` 名下
    for i in range(len(low)):
        cand = low[:i] + low[i + 1:]
        if len(cand) >= 3 and zipf(cand) > score + 1.0:
            best, score = cand, zipf(cand)
    return best


def bad_head(w):
    """词头站不住就整条不要：虚词、小品词标题、纠错之后还不是真词。"""
    return (w.lower() in NOT_HEAD or w.isupper() or len(w) < 2
            or not re.fullmatch(r"[a-z][a-z'\-]*", w) or zipf(w) < 1.6)


def is_entry_start(line, t, x0):
    """条目起始行：**外凸**（悬挂缩进）+ 带重音符号 + 以小写英文起头。

    悬挂缩进是这本书最硬的判据：条目行 x 约等于栏左边界，续行往里缩 0.015。
    光看重音符号不行——释义里引的短语动词也带重音（`SYN cheer sb up`）。
    """
    if line["x"] > x0 + 0.010:
        return False
    if not ACCENT.search(t[:40]):
        return False
    if not re.match(r"^[a-zˈˌ(]", t):
        return False
    return True


def parse_page(page):
    """产出 [{kind: head|entry|pat|label|cont, ...}]，按栏内自然顺序。"""
    out = []
    for col in columns(page):
        if not col:
            continue
        x0 = col_x0(col)
        for line in col:
            t = normalize(line["t"])
            if len(t) < 2:
                continue
            hd = head_of(t)
            if hd and line["x"] <= x0 + 0.015 and not ACCENT.search(hd[0]):
                out.append({"kind": "head", "word": hd[0],
                            "ipa": hd[1], "tail": hd[2]})
                continue
            if PAT_RE.match(t):
                out.append({"kind": "pat", "text": t})
                continue
            lab, rest = label_of(t)
            if lab:
                out.append({"kind": "label", "label": lab, "text": rest})
                continue
            if is_entry_start(line, t, x0):
                out.append({"kind": "entry", "text": t})
                continue
            out.append({"kind": "cont", "text": t})
    return out


def keep_alphabetical(words):
    """词典是按字母排的：**排不进字母序的词头就是假的**。

    正文里的词加个斜杠就能冒充词头（`call` 词条里的 `brigade /…`、
    `get` 里的 `clearly /…`），单看这一条分辨不出来，放到序列里一眼就露馅。
    取最长不下降子序列——留下的词头数最多，被挤掉的就是插错位的那些。
    相等要保留（同一个动词的名词义会再出一次词头）。

    返回要保留的下标集合。
    """
    if not words:
        return set()
    ends, back = [], [-1] * len(words)      # ends[k] = 长度 k+1 的子序列末尾下标
    import bisect
    tails = []
    for i, w in enumerate(words):
        k = bisect.bisect_right(tails, w)
        if k == len(tails):
            tails.append(w)
            ends.append(i)
        else:
            tails[k] = w
            ends[k] = i
        back[i] = ends[k - 1] if k else -1
    keep, i = set(), ends[-1]
    while i >= 0:
        keep.add(i)
        i = back[i]
    return keep


def main():
    os.makedirs(OUT, exist_ok=True)
    heads, orphan = [], []
    for n in range(FIRST_PDF_PAGE, LAST_PDF_PAGE + 1):
        p = os.path.join(OCR, f"p{n:03d}.json")
        if not os.path.exists(p):
            continue
        book = n - FIRST_PDF_PAGE + FIRST_BOOK_PAGE
        for it in parse_page(json.load(open(p))):
            if it["kind"] == "head":
                w = fix_word(it["word"])
                if bad_head(w):
                    continue          # `OVER`、`sb`、`if` 这些不是词头
                # 同一个词头连着出现两次（跨页续排、或 gapfill 补重了），
                # 后面那次不另开词条，接着往前一个里放
                if heads and heads[-1]["word"] == w:
                    continue
                heads.append({"word": w, "ipa": it["ipa"],
                              "infl": it["tail"], "page": book, "entries": []})
                continue
            if not heads:
                orphan.append(it)
                continue
            es = heads[-1]["entries"]
            if it["kind"] == "entry":
                es.append({"raw": it["text"], "pats": [], "labels": [],
                           "page": book})
            elif not es:
                orphan.append(it)
            elif it["kind"] == "pat":
                es[-1]["pats"].append(it["text"])
            elif it["kind"] == "label":
                es[-1]["labels"].append([it["label"], it["text"]])
            else:
                # 续行接到条目块尾巴上。断词连字符要在拼接时抹掉
                es[-1]["raw"] = (es[-1]["raw"][:-1] + it["text"]
                                 if es[-1]["raw"].endswith("-")
                                 else es[-1]["raw"] + " " + it["text"])

    # 假词头挤掉之后，它名下的条目要还给**前一个**活着的词头——
    # 那些条目本来就是前一个词条的正文（`brigade` 是 `call` 词条里的一个词）
    keep = keep_alphabetical([h["word"] for h in heads])
    merged, dropped = [], []
    for i, h in enumerate(heads):
        if i in keep or not merged:
            merged.append(h)
        else:
            dropped.append(h["word"])
            merged[-1]["entries"] += h["entries"]
    heads = merged

    json.dump(heads, open(os.path.join(DATA, "entries.json"), "w"),
              ensure_ascii=False, indent=1)
    n_e = sum(len(h["entries"]) for h in heads)
    print(f"排不进字母序、被挤掉的假词头 {len(dropped)} 个：{dropped[:12]}")
    lines = ["# 牛津短语动词词典 · 词条清单\n",
             f"\n词头 {len(heads)} 个，短语动词条目 {n_e} 条，"
             f"无主碎行 {len(orphan)} 条。`p` 是书内页码。\n"]
    for h in heads:
        lines.append(f"\n## {h['word']} /{h['ipa']}/  <sub>p{h['page']}</sub>\n")
        for e in h["entries"]:
            lines.append(f"- {e['raw']}")
            for lab, txt in e["labels"]:
                lines.append(f"  - **{lab}** {txt}")
            for p_ in e["pats"]:
                lines.append(f"  - `{p_}`")
    open(os.path.join(OUT, "词条清单.md"), "w").write("\n".join(lines) + "\n")
    print(f"词头 {len(heads)}，条目 {n_e}，无主碎行 {len(orphan)}")
    print(os.path.join(OUT, "词条清单.md"))


if __name__ == "__main__":
    main()
