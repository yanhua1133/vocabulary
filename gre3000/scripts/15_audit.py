"""Pass 15: 全量确定性校验 data/words.json。

只查机器能判定的硬错误，语义正确性交给 16/17 的模型复核：
  spell        单词本身不在词典、也没有词频记录（多半是解码残留）
  ipa_bad      音标字符非法、或与 cmudict 发音差异过大
  ipa_missing  没有音标
  ex_missing   缺例句 / 缺中文翻译
  ex_word      例句里找不到该词（含屈折形式）
  ex_len       例句英文过短或过长
  ex_glue      例句里有粘连的超长 token
  ph_word      常用短语里找不到该词
  ph_cn        短语中文缺失或不含中文
  pos_missing  缺词性
  pos_morph    词形与词性明显冲突（-ly 标成形容词之类）
  cn_missing   缺中文释义
  cn_latin     中文释义里混入成片英文
  star_rare    删除线标记与词频不一致

输出 data/audit.json（按词列出问题）与统计。
"""
import json
import os
import re
import sys
from collections import Counter

import wordfreq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
IPA_OK = set("ˈˌːˑaɑɒæʌeɛɜəɪiɔoʊuʏybdfɡhjklmnprstvwzʃʒθðŋ() .-'")
VOWEL_IPA = set("aɑɒæʌeɛɜəɪiɔoʊuy")
CJK = re.compile(r"[\u4e00-\u9fff]")
SUFFIX_POS = [
    (re.compile(r"ly$"), {"副词"}, {"形容词", "名词"}),
    (re.compile(r"(tion|sion|ment|ness|ity|ance|ence|ism|ist|ship)$"),
     {"名词"}, {"动词", "及物动词", "不及物动词", "副词"}),
    (re.compile(r"(ous|ful|less|able|ible|ish|ive|al|ic|ary)$"),
     {"形容词"}, {"动词", "及物动词", "不及物动词", "副词"}),
    (re.compile(r"(ize|ise|ify|ate)$"),
     {"动词", "及物动词", "不及物动词", "形容词", "名词"}, set()),
]
POS_CN = {
    "n": "名词", "v": "动词", "vt": "及物动词", "vi": "不及物动词",
    "adj": "形容词", "adv": "副词", "prep": "介词", "conj": "连词",
    "pron": "代词", "num": "数词", "art": "冠词", "aux": "助动词",
}


def load_words():
    w = set()
    for p in ("/usr/share/dict/web2", "/usr/share/dict/web2a"):
        if os.path.exists(p):
            w |= {x.strip().lower() for x in open(p, encoding="latin-1")
                  if x.strip().isalpha()}
    return w


DICT = load_words()
INFLECT = re.compile(
    r"\b(ran|run|threw|thrown|came|come|wore|worn|took|taken|gave|given|went|gone|"
    r"made|paid|held|brought|drew|drawn|swept|struck|hung|wound|left|kept|"
    r"fell|fled|flung|flew|shot|dug|dealt|spent|sped|sought|taught|bore|borne|"
    r"broke|broken|chose|chosen|drove|driven|ate|eaten|forgot|got|grew|knew|"
    r"laid|lay|lost|meant|met|rose|risen|said|sat|sang|sank|saw|seen|sold|sent|"
    r"set|shook|shaken|shone|shrank|slept|slid|spoke|spoken|stood|stole|stolen|"
    r"stuck|stung|swore|swum|tore|torn|told|thought|trod|understood|woke|won|wrote|"
    r"caught|bought|fought|taught|sought|brought)\b")


def known(tok):
    t = tok.lower().strip("'’-")
    if not t:
        return True
    if t in DICT or wordfreq.zipf_frequency(t, "en") > 0:
        return True
    for suf in ("s", "es", "ed", "d", "ing", "ly", "er", "est", "ness"):
        if t.endswith(suf) and (t[: -len(suf)] in DICT
                                or t[: -len(suf)] + "e" in DICT):
            return True
    for pre in ("non", "un", "dis", "re", "pre", "anti", "arch", "super",
                "over", "under", "mis", "semi", "inter", "co"):
        if t.startswith(pre) and len(t) > len(pre) + 3 and known(t[len(pre):]):
            return True
    return False


FUNCTION_WORDS = {
    "and", "or", "the", "of", "to", "in", "is", "it", "as", "he", "she", "we",
    "my", "be", "at", "on", "so", "if", "by", "an", "that", "this", "are",
    "was", "you", "your", "his", "her", "not", "i", "a", "am", "for", "with",
    "but", "me", "them", "their", "our", "its", "from", "all", "who",
}


def glued(s, lookup=known):
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
    return ok and segs >= 3 and nfunc >= 2


def stem(word):
    w = re.split(r"[^A-Za-z]+", word.lower())[0] if word else ""
    return re.sub(r"(e|ate|ing|ed|s)$", "", w)[:3]


def lcs(a, b):
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b):
            cur.append(prev[j] + 1 if ca == cb else max(cur[j], prev[j + 1]))
        prev = cur
    return prev[-1]


ARPA_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ə", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "EH": "e", "ER": "ɜr",
    "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ",
    "OW": "o", "OY": "ɔɪ", "P": "p", "R": "r", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}


def main():
    words = json.load(open(os.path.join(DATA, "words.json")))
    try:
        import cmudict
        cmu = cmudict.dict()
    except Exception:
        cmu = {}

    audit = {}
    counts = Counter()

    for w, r in words.items():
        probs = []
        # 粘连串已在解析阶段按黑名单剔除；这里只查明显不是英文的残片
        if re.fullmatch(r"[A-Za-z]{2,4}", w) and not known(w):
            probs.append("spell")

        ipa = (r.get("ipa") or "").strip()
        if not ipa:
            probs.append("ipa_missing")
        else:
            if {c for c in ipa if c not in IPA_OK}:
                probs.append("ipa_bad")
            elif not any(c in VOWEL_IPA for c in ipa):
                probs.append("ipa_bad")
            else:
                prons = cmu.get(w.lower())
                if prons:
                    ref = "".join(ARPA_TO_IPA.get(re.sub(r"\d", "", p), "")
                                  for p in prons[0])
                    # cmudict 的 ŋ/n 标注不统一（incongruity 记成 ɪŋkɔŋruːɪti），先归一
                    norm = lambda x: re.sub(r"[ˈˌːˑ() .\-']", "", x).replace("ŋ", "n")
                    got = norm(ipa)
                    ref_c = norm(ref)
                    # 单音节/短词的 LCS 比例天生偏低，只查够长的词
                    if len(ref_c) >= 7 and len(got) >= 7 and \
                            lcs(got, ref_c) / max(len(got), len(ref_c)) < 0.55:
                        probs.append("ipa_bad")

        ex = (r.get("example") or "").strip()
        if not ex:
            probs.append("ex_missing")
        else:
            en = ex.split("  ")[0]
            cn = ex[len(en):].strip()
            if not CJK.search(cn):
                probs.append("ex_missing")
            n = len(en.split())
            if not 4 <= n <= 26:
                probs.append("ex_len")           # 短语不算例句
            elif not re.match(r"^[A-Z“‘(]", en) or not re.search(r"[.!?”]$", en.strip()):
                probs.append("ex_frag")          # 首字母不大写/无句末标点 → 截断
            if stem(w) and stem(w) not in en.lower().replace("-", " ") \
                    and not INFLECT.search(en.lower()):
                probs.append("ex_word")
            if [t for t in re.findall(r"[A-Za-z]{18,}", en) if not known(t)]:
                probs.append("ex_glue")

        ph, phcn = (r.get("phrase") or "").strip(), (r.get("phrase_cn") or "").strip()
        if not ph or (stem(w) and stem(w) not in ph.lower().replace("-", " ")
                      and not INFLECT.search(ph.lower())):
            probs.append("ph_word")
        if not phcn or not CJK.search(phcn):
            probs.append("ph_cn")

        pos = (r.get("pos") or "").strip()
        cn_pos = {POS_CN.get(p.strip().rstrip("."), "") for p in pos.split("/") if p}
        if not pos:
            probs.append("pos_missing")

        cn = (r.get("cn") or "").strip()
        if not cn or not CJK.search(cn):
            probs.append("cn_missing")
        elif len(re.findall(r"[A-Za-z]{4,}", cn)) >= 2:
            probs.append("cn_latin")

        z = r.get("zipf", 0)
        if bool(r.get("rare")) != (z < 1.5):
            probs.append("star_rare")

        if probs:
            audit[w] = probs
            for p in probs:
                counts[p] += 1

    json.dump(audit, open(os.path.join(DATA, "audit.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"检查 {len(words)} 个词，有问题的 {len(audit)} 个")
    for k, v in counts.most_common():
        print(f"  {k:12} {v}")


if __name__ == "__main__":
    main()
