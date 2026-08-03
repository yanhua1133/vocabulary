"""Pass 10: turn decoded pages into data/book.json.

Structure per entry:
  {word, ipa, senses:[{pos, cn, en}], examples:[{en, cn}],
   syn:[..], ant:[..], deriv:[..], page}
grouped as list -> unit -> entries.

Text-level cleanup happens here rather than in the glyph labels: stray internal
capitals are lowered, and semicolon separators that decoded as a trailing "s"
are restored by dictionary lookup.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from decode import Decoder

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

HEAD_FACE = "DLF-3-82"
UNIT_FACE = "DLF-3-55"
LIST_FACE = "DLF-3-91"
BLUE = 0x00AEEF
WHITE = 0xFFFFFF
CJK = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")
POS_MAP = {
    "edh.": "adj.", "edh": "adj.", "h.": "v.", "ht.": "vt.", "hi.": "vi.",
    "n.": "n.", "e.": "n.", "rEf.": "adj.", "adA.": "adj.", "adh.": "adj.",
    "ah.": "adv.", "pEs": "vt.", "pE.": "vt.", "prep.": "prep.",
    "conJ.": "conj.", "conj.": "conj.", "pron.": "pron.", "art.": "art.",
    "num.": "num.", "aux.": "aux.", "vt.": "vt.", "vi.": "vi.", "v.": "v.",
    "adj.": "adj.", "adv.": "adv.",
}


def load_words():
    words = set()
    for p in ("/usr/share/dict/web2", "/usr/share/dict/web2a"):
        if os.path.exists(p):
            words |= {w.strip().lower() for w in open(p, encoding="latin-1")
                      if w.strip().isalpha()}
    return words


WORDS = load_words()


def in_dict(w):
    w = w.lower()
    if w in WORDS:
        return True
    for suf in ("s", "es", "d", "ed", "ing"):
        if w.endswith(suf) and w[: -len(suf)] in WORDS:
            return True
    return False


def clean(text):
    """Undo the two decode artefacts that survive into words."""
    def fix_token(m):
        t = m.group(0)
        if t.isupper() or len(t) < 2:
            return t
        t = t[0] + t[1:].lower()
        if t[0].isupper() and t.lower() in WORDS:
            t = t.lower()
        return t
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)      # 行末断词接回
    text = re.sub(r"[A-Za-z][A-Za-z'’-]*", fix_token, text)
    # "unyieldings inflexible" -> "unyielding; inflexible"
    def fix_sep(m):
        w = m.group(1)
        return (w + ";" if not in_dict(w + "s") or in_dict(w) else w + "s") + " "
    text = re.sub(r"\b([a-z]{3,})s(?= [a-z])", lambda m: (
        m.group(1) + ";" if (not in_dict(m.group(1) + "s") and in_dict(m.group(1)))
        else m.group(0)), text)
    return re.sub(r"\s+", " ", text).strip()


def split_en_cn(text):
    m = CJK.search(text)
    if not m:
        return clean(text), ""
    return clean(text[: m.start()]), text[m.start():].strip()


# 原书例句/名言/断行残片被当成词条漏进词表，逐个确认后拉黑
JUNK = {"ofothermen", "livinganddead", "heartandsoul", "youareanartist",
        "triestouseit", "glowingtribute", "aproposof", "asfaras", "asfor",
        "asregards", "perfidytreachery", "obdurateopinionated",
        "interrupteddiscontinuous", "paradoxicalimplausible", "locale location",
        "keen on title", "humbuggery e", "ibarelyremember", "anythingelse",
        "interferewith", "disasterbane", "scionable", "manent", "meled",
        "pede", "plex", "some", "cious", "trant", "diced", "ishing", "el",
        "pated", "ciliousness", "fied", "ent", "wanttoputonfaces", "dering",
        "dinate", "menable", "everyman'swork", "clannish ref", "wincharge",
        "overestimateexaggerate"}

SPELL_FIX = {"blas": "blasé", "clat": "éclat", "clich": "cliché",
             "nave": "naive", "outr": "outré", "prcis": "précis",
             "conservational": "conversational", "tumoil": "turmoil",
             "adament": "adamant", "bootout": "boot out",
             "castout": "cast out", "drumout": "drum out",
             "kickout": "kick out", "passover": "pass over",
             "cutacross": "cut across", "proceedalong": "proceed along",
             "thickskinned": "thick-skinned", "selfabasement": "self-abasement",
             "stumblingblock": "stumbling block", "hamhanded": "ham-handed"}

IPA_JUNK = re.compile(r"[ˈˌːæəɪʊɜɑɒʌʃʒθðŋ［］\[\]]")


FUNCTION_WORDS = {
    "and", "or", "the", "of", "to", "in", "is", "it", "as", "he", "she", "we",
    "my", "be", "at", "on", "so", "if", "by", "an", "that", "this", "are",
    "was", "you", "your", "his", "her", "not", "i", "a", "am", "for", "with",
    "but", "me", "them", "their", "our", "its", "from", "all", "who",
}


def glued_sentence(s, lookup):
    """原书例句/名言被粘成一个 token 漏进词表，例如 ofothermen、Ibarelyremember。

    枚举所有切分（不能贪心：ofothermen 会被贪心切成 ofo+therm+en），
    只要存在一种切分同时满足「>=3 段」和「>=2 个虚词」就判为粘连句。
    整串本身是词典词的直接放过，所以 islander 之类不会误伤。
    """
    from functools import lru_cache

    t = s.lower()
    if len(t) < 8 or " " in t or "-" in t or lookup(t):
        return False
    n = len(t)

    @lru_cache(None)
    def go(i):
        """从 i 切到结尾：(能否切完, 最多段数, 最多虚词数)"""
        if i == n:
            return (True, 0, 0)
        ok, best, nfunc = False, 0, 0
        for j in range(i + 1, min(n, i + 12) + 1):
            p = t[i:j]
            if not (len(p) >= 2 or p in ("i", "a")) or not lookup(p):
                continue
            done, cnt, nf = go(j)
            if done:
                ok = True
                best = max(best, cnt + 1)
                nfunc = max(nfunc, nf + (1 if p in FUNCTION_WORDS else 0))
        return (ok, best, nfunc)

    ok, segs, nfunc = go(0)
    return ok and segs >= 3 and nfunc >= 3


def is_wordlike(s):
    if not s or len(s) > 40 or len(s.split()) > 4:
        return False
    if IPA_JUNK.search(s) or not re.search(r"[aeiouy]", s, re.I):
        return False
    if s.isupper() or not re.match(r"^[A-Za-z]", s):
        return False
    if s.endswith("-"):
        return False                       # 行末断词碎片
    if s.lower() in JUNK:
        return False
    if glued_sentence(s, in_dict):
        return False                       # 粘连的整句（原书例句/名言漏进词表）
    return True


def split_items(text):
    en, cn = split_en_cn(text)
    items = [x.strip(" .") for x in re.split(r"[;,]|\bor\b", en) if x.strip(" .")]
    return [SPELL_FIX.get(i.lower(), i) for i in items if is_wordlike(i)], cn


def parse_sense(text):
    """'【考法1】adj. 富裕的：having a generously ...'"""
    body = re.sub(r"^【[^】]*】", "", text).strip()
    body = re.sub(r"^［[^］]*］", "", body).strip()
    pos = ""
    m = re.match(r"((?:[A-Za-z]{1,4}\.)(?:/[A-Za-z]{1,4}\.)*)", body)
    if m:
        parts = [x for x in m.group(1).split("/") if x]
        mapped = [POS_MAP.get(x) for x in parts]
        if all(mapped):
            pos = "/".join(dict.fromkeys(mapped))
            body = body[m.end():]
    cn, en = body, ""
    if "：" in body:
        cn, en = body.split("：", 1)
    cn = IPA_JUNK.sub("", cn).strip(" ；;：:")
    if not CJK.search(cn):                 # 没有中文说明切错了，当英文释义
        en, cn = (cn + " " + en).strip(), ""
    return {"pos": pos.strip(), "cn": cn, "en": clean(en)}


def main():
    dec = Decoder()
    lists = []
    cur_list = cur_unit = cur_entry = None
    mode = None

    for pno in range(len(dec.res.doc)):
        lines = dec.spans(pno)
        ipa_items = dec.ipa_items(pno)
        buckets = {}
        for line in lines:
            for sp in line:
                if not sp["text"].strip() or sp["face"].startswith("Helvetica"):
                    continue
                if sp["color"] == 0x808285:          # grey unit index box
                    continue
                key = round((sp["bbox"][1] + sp["bbox"][3]) / 2 / 3.0)
                buckets.setdefault(key, []).append(sp)
        rows = []
        for key in sorted(buckets):
            sps = sorted(buckets[key], key=lambda s: s["bbox"][0])
            text = "".join(s["text"] for s in sps).strip()
            if text:
                rows.append((min(s["bbox"][1] for s in sps), text, sps))

        for y, text, line in rows:
            faces = {s["face"] for s in line}
            colors = {s["color"] for s in line}
            sizes = max(s["size"] for s in line)

            if LIST_FACE in faces and sizes >= 25:
                m = re.search(r"(\d+)", text)
                num = int(m.group(1)) if m else len(lists) + 1
                cur_list = {"list": num, "units": []}
                lists.append(cur_list)
                cur_unit = cur_entry = None
                continue
            if UNIT_FACE in faces:
                m = re.search(r"Unit\s*(\d+)", text)
                if m:
                    if cur_list is None:
                        cur_list = {"list": 1, "units": []}
                        lists.append(cur_list)
                    cur_unit = {"unit": int(m.group(1)), "entries": []}
                    cur_list["units"].append(cur_unit)
                    cur_entry = None
                continue
            if any(s["face"] == HEAD_FACE and s["size"] >= 8.3 and s["color"] == BLUE
                   for s in line):
                word = "".join(s["text"] for s in line
                               if s["face"] == HEAD_FACE and s["size"] >= 8.3
                               and s["color"] == BLUE)
                word = clean(word.split("［")[0])
                word = SPELL_FIX.get(word.lower(), word)
                if not is_wordlike(word):
                    continue
                if cur_unit is None:
                    if cur_list is None:
                        cur_list = {"list": 1, "units": []}
                        lists.append(cur_list)
                    cur_unit = {"unit": 0, "entries": []}
                    cur_list["units"].append(cur_unit)
                near = [i for i in ipa_items if abs(i["y"] - (y + sizes / 2)) < 6]
                cur_entry = {"word": word, "ipa": near[0]["text"] if near else "",
                             "senses": [], "examples": [], "syn": [], "ant": [],
                             "deriv": [], "page": pno}
                cur_unit["entries"].append(cur_entry)
                mode = None
                continue
            if cur_entry is None:
                continue
            marker = {"例": "ex", "近": "syn", "反": "ant", "派": "deriv"}
            if text[0] in marker:
                mode = marker[text[0]]
                text = text[1:].strip()
                if not text:
                    continue
            if text.startswith("【考法"):
                cur_entry["senses"].append(parse_sense(text))
                mode = "sense"
                continue
            if mode == "ex":
                for part in text.split("‖"):
                    en, cn = split_en_cn(part)
                    if en:
                        cur_entry["examples"].append({"en": en, "cn": cn})
            elif mode in ("syn", "ant"):
                items, cn = split_items(text)
                cur_entry[mode].extend(items)
                if cn and mode == "ant":
                    cur_entry.setdefault("ant_cn", cn)
            elif mode == "deriv":
                cur_entry["deriv"].append(clean(text))
            elif mode == "sense" and cur_entry["senses"]:
                cur_entry["senses"][-1]["en"] += " " + clean(text)

    # drop front matter: keep lists that actually contain units with entries
    lists = [L for L in lists
             if sum(len(u["entries"]) for u in L["units"]) > 0]
    for L in lists:
        L["units"] = [u for u in L["units"] if u["entries"]]
    out = {"lists": lists}
    json.dump(out, open(os.path.join(DATA, "book.json"), "w"),
              ensure_ascii=False, indent=1)
    n_units = sum(len(L["units"]) for L in lists)
    n_entries = sum(len(u["entries"]) for L in lists for u in L["units"])
    n_syn = sum(len(e["syn"]) for L in lists for u in L["units"] for e in u["entries"])
    n_ant = sum(len(e["ant"]) for L in lists for u in L["units"] for e in u["entries"])
    print(f"lists={len(lists)} units={n_units} entries={n_entries} "
          f"syn={n_syn} ant={n_ant}")
    noipa = [e["word"] for L in lists for u in L["units"] for e in u["entries"]
             if not e["ipa"]]
    print(f"entries without ipa: {len(noipa)} e.g. {noipa[:8]}")


if __name__ == "__main__":
    main()
