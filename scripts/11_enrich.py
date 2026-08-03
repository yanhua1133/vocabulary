"""Pass 11: add the objective columns to every word that will appear in a row.

Objective, reproducible, no model opinion:
  常用度★  from wordfreq Zipf
  极其罕见   Zipf < 1.5  -> the row gets struck through
  口语度★  from Zipf minus a written-register penalty for academic morphology
  音标      book transcription for headwords, cmudict->IPA for 近/反 rows

Model-written columns (中文释义 for 近/反 rows, 常用短语, 例句) are read from
data/enrich_cache.json if present and left blank otherwise, so this pass is
always cheap and re-runnable.

Output: data/words.json  {word: {...}} plus data/todo_llm.json (what is missing)
"""
import json
import os
import re
import sys

import wordfreq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# 辅音
CONS = {
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p",
    "R": "r", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}
# 元音分重读/非重读两套写法：重读用长音与 ʌ，非重读弱化
VOWEL_STRESSED = {
    "AA": "ɑː", "AE": "æ", "AH": "ʌ", "AO": "ɔː", "AW": "aʊ", "AY": "aɪ",
    "EH": "e", "ER": "ɜːr", "EY": "eɪ", "IH": "ɪ", "IY": "iː", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "uː",
}
VOWEL_WEAK = {
    "AA": "ɑ", "AE": "æ", "AH": "ə", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "EH": "e", "ER": "ər", "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
}
WRITTEN_SUFFIX = ("tion", "sion", "ity", "ous", "ate", "ism", "ance", "ence",
                  "acy", "ency", "itude", "escence", "iferous", "ory", "ary")


def zipf(word):
    parts = [p for p in re.split(r"[^A-Za-z’'-]+", word) if p]
    if not parts:
        return 0.0
    return min(wordfreq.zipf_frequency(p.lower(), "en") for p in parts)


def stars_common(z):
    """Zipf 词频线性映射到 0-5 的半星刻度（0.5 一档）。"""
    v = (z - 1.4) / 0.9
    return max(0.0, min(5.0, round(v * 2) / 2))


def stars_spoken(word, z):
    s = stars_common(z)
    w = word.lower()
    if any(w.endswith(x) for x in WRITTEN_SUFFIX):
        s -= 1.5
    if len(w) >= 11:
        s -= 1
    if " " in w or "-" in w:
        s -= 0.5
    return max(0.0, min(5.0, round(s * 2) / 2))


ONSET2 = {("T", "R"), ("D", "R"), ("P", "R"), ("B", "R"), ("K", "R"),
          ("G", "R"), ("F", "R"), ("TH", "R"), ("S", "T"), ("S", "P"),
          ("S", "K"), ("S", "L"), ("S", "M"), ("S", "N"), ("S", "W"),
          ("P", "L"), ("B", "L"), ("K", "L"), ("G", "L"), ("F", "L"),
          ("T", "W"), ("K", "W"), ("HH", "Y"), ("SH", "R")}


def onset_start(phones, v):
    """重读元音 v 的音节起点。

    整个辅音簇在词首时全归本音节；否则带走一个辅音，若再往前一个能与它
    构成合法起首簇（tr/st/pl…）就再带一个 —— 否则会切出 ˈfrʌstˌreɪt 这种。
    """
    bare = [re.sub(r"\d", "", p) for p in phones]
    c = v
    while c > 0 and bare[c - 1] in CONS:
        c -= 1
    if c == 0:
        return 0
    start = v - 1
    if start - 1 >= c and (bare[start - 1], bare[start]) in ONSET2:
        start -= 1
    return start


def ipa_from_cmu(cmu, word):
    key = word.lower().strip()
    prons = cmu.get(key)
    if not prons:
        return ""
    phones = prons[0]
    primary = next((i for i, p in enumerate(phones) if p.endswith("1")), None)
    secondary = next((i for i, p in enumerate(phones) if p.endswith("2")), None)
    marks = {}
    if primary is not None:
        marks[onset_start(phones, primary)] = "ˈ"
    if secondary is not None:
        pos = onset_start(phones, secondary)
        marks.setdefault(pos, "ˌ")
    out = []
    for i, ph in enumerate(phones):
        if i in marks:
            out.append(marks[i])
        base = re.sub(r"\d", "", ph)
        if base in CONS:
            out.append(CONS[base])
        elif ph.endswith("1") or ph.endswith("2"):
            out.append(VOWEL_STRESSED.get(base, ""))
        else:
            out.append(VOWEL_WEAK.get(base, ""))
    return "".join(out)


def main():
    book = json.load(open(os.path.join(DATA, "book.json")))
    cache_path = os.path.join(DATA, "enrich_cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    try:
        import cmudict
        cmu = cmudict.dict()
    except Exception:
        cmu = {}

    words = {}

    def add(word, kind, pos_hint="", ipa="", cn=""):
        key = word.strip()
        if not key or len(key) > 40:
            return
        rec = words.get(key)
        z = zipf(key)
        if rec is None:
            rec = words[key] = {
                "word": key, "kind": kind, "zipf": round(z, 2),
                "common": stars_common(z), "spoken": stars_spoken(key, z),
                "rare": z < 1.5, "pos": pos_hint,
                "ipa": ipa or ipa_from_cmu(cmu, key), "cn": cn,
                "phrase": "", "phrase_cn": "", "example": "",
            }
        else:
            if kind == "head":
                rec["kind"] = "head"
            if ipa and not cache.get(key.lower(), {}).get("ipa"):
                rec["ipa"] = ipa
            if cn and not rec["cn"]:
                rec["cn"] = cn
            if pos_hint and not rec["pos"]:
                rec["pos"] = pos_hint
        c = cache.get(key.lower(), {})
        for f in ("cn", "phrase", "phrase_cn", "example", "pos", "spoken"):
            if c.get(f):
                rec[f] = c[f]
        if c.get("ipa"):
            rec["ipa"] = c["ipa"]        # 缓存里的音标经过模型复核，优先

    for L in book["lists"]:
        for u in L["units"]:
            for e in u["entries"]:
                parts = [x for s in e["senses"] for x in s["pos"].split("/") if x]
                pos = "/".join(dict.fromkeys(parts))
                cn = "；".join(s["cn"] for s in e["senses"] if s["cn"])
                # 原书例句解码后普遍丢空格、被截断、以小写开头，一律不用；
                # 例句统一由模型写，缓存在 enrich_cache.json。
                add(e["word"], "head", pos, e["ipa"], cn)
                for w in e["syn"]:
                    add(w, "syn")
                for w in e["ant"]:
                    add(w, "ant")

    json.dump(words, open(os.path.join(DATA, "words.json"), "w"),
              ensure_ascii=False, indent=1)

    todo = sorted(w for w, r in words.items()
                  if not r["cn"] or not r["phrase"] or not r.get("phrase_cn")
                  or not r["example"] or not r["ipa"])
    json.dump(todo, open(os.path.join(DATA, "todo_llm.json"), "w"),
              ensure_ascii=False, indent=1)

    heads = sum(1 for r in words.values() if r["kind"] == "head")
    rare = sum(1 for r in words.values() if r["rare"])
    noipa = sum(1 for r in words.values() if not r["ipa"])
    print(f"words={len(words)} (head={heads}) rare={rare} no-ipa={noipa}")
    print(f"needing model fields: {len(todo)}")


if __name__ == "__main__":
    main()
