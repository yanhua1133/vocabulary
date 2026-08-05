"""Pass 10: 清理从扫描件抽出来的原书例句 → data/examples.json。

原书例句是词典的权威内容，能用就该用，只有确实被 OCR 毁掉的才退回自写例句。
抽出来的 5257 条里大部分是干净的，坏的是些固定套路：

- `T've` / `Tm` → `I've` / `I'm`（大写 I 被认成 T）
- `Im` / `Il` → `I'm` / `I'll`（撇号丢了）
- `WaS`、`tHe` 这类词中间冒出大写字母
- 中文里插进空格、英文数字与汉字之间缺空格
- 句子被截断（没有结尾标点、或以介词冠词收尾）

Usage: 10_clean_ex.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CJK = re.compile(r"[\u4e00-\u9fff]")
TRUNC = re.compile(r"\b(a|an|the|of|to|in|on|at|for|with|and|or|from|by|"
                   r"that|his|her|my|your|their|is|are|was|were)$", re.I)


def clean_en(t):
    t = t.strip(" •◆◇*·-—")
    t = re.sub(r"^[/1l|]\s+(?=[a-z])", "I ", t)         # 句首的 I 被认成 / 1 l |
    t = re.sub(r"^([/1|])(?=[a-z'])", "I", t)
    t = re.sub(r"\bT'(ve|re|ll|m|d)\b", r"I'\1", t)      # T've → I've
    t = re.sub(r"\bT\b", "I", t)
    t = re.sub(r"\bIm\b", "I'm", t)
    t = re.sub(r"\bIl\b", "I'll", t)
    t = re.sub(r"\bIve\b", "I've", t)
    t = re.sub(r"\bdont\b", "don't", t)
    t = re.sub(r"\bcant\b", "can't", t)
    # 大小写乱掉的词（`WaS`、`tHe`）整个转小写；首字母大写和全大写的不动
    def case(m):
        w = m.group(0)
        if w in (w.lower(), w.capitalize(), w.upper()):
            return w
        return w.lower()

    t = re.sub(r"\b[A-Za-z]{2,}\b", case, t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def clean_cn(t):
    t = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", t)
    t = t.replace(",", "，").replace(";", "；").replace("?", "？")
    t = re.sub(r"[。．]{2,}", "。", t)
    t = re.sub(r"[，。；]+$", "。", t)
    return re.sub(r"\s+", " ", t).strip(" ·•*")


def usable(en, cn, idiom):
    """够不够格用作例句：完整句、有中译、且真的用上了这条习语。"""
    if len(en.split()) < 4 or not CJK.search(cn):
        return False
    if not en[0].isupper():
        return False
    if not en.rstrip().endswith((".", "!", "?", "'", "\u201d")):
        # 没有句末标点才算截断；`How about Ruth? Have you heard from her?`
        # 是完整的两句，不能因为末词是 her 就判成半句
        return False if TRUNC.search(en.rstrip()) else False
    # 只拒绝汉字和混进来的重音符号；破折号、弯引号、重音字母都是正常英文排版
    if CJK.search(en) or "ˈ" in en or "ˌ" in en:
        return False
    core = [w for w in re.findall(r"[a-z]{4,}",
                                  re.sub(r"\([^)]*\)", "", idiom).lower())
            if w not in ("sth", "sbs", "your", "yours", "that", "this", "with",
                         "have", "been", "from", "into", "them", "they", "etc")]
    low = en.lower()
    # 按词干比，例句里的习语常有屈折变化（`take ˈaim` → `taking aim`）
    return not core or any(w[:max(3, len(w) - 2)] in low for w in core)


def main():
    book = json.load(open(os.path.join(DATA, "idioms.json")))
    out, kept, total = {}, 0, 0
    idx = 0
    for h in book:
        for it in h["idioms"]:
            key = str(idx)
            idx += 1
            en, cn = clean_en(it["ex_en"]), clean_cn(it["ex_cn"])
            if not en:
                continue
            total += 1
            if usable(en, cn, it["idiom"]):
                out[key] = {"en": en, "cn": cn}
                kept += 1
    json.dump(out, open(os.path.join(DATA, "examples.json"), "w"),
              ensure_ascii=False, indent=0)
    print(f"抽到原书例句 {total} 条，清理后可用 {kept} 条（{kept/max(total,1):.0%}）")
    for k in list(out)[:5]:
        print(f"   {out[k]['en'][:66]}")
        print(f"   {out[k]['cn'][:40]}")


if __name__ == "__main__":
    main()
