#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 makeex 批次用的小工具：
  show  NNNN [start] [count]   打印待写条目（编号 + coll[0] + cn）
  build NNNN                   把 work/makeex/NNNN.txt (编号<TAB>英<TAB>中) 合成 NNNN.out.json 并自查
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'work', 'makeex')
PARTS = os.path.join(ROOT, 'work', 'makeex_parts')

TAGS = re.compile(r'\([^)]*\)?')
# OCR 把两个词粘死、拼不回来的碎片，例句写不进去，自查时跳过
JUNK = set('''increasstarted temin conagainst completegreat bodydancing neri implipublicly cardiodisfigure architechnical increasuformaton ingly mermethane proacknowledged'''.split())

STOP = set('''esp amE bre ame althea anthe figurative humorous literary usually

a an the of to in on for at by with from into onto over under about as and or but not
sb sb's sth sth's your yours you it its his her their our my this that these those be been being
is are was were am do does did done have has had will would can could may might must shall should
no any some all more most much many very too so such other another each every one two'''.split())


def load(batch):
    return json.load(open(os.path.join(DIR, batch + '.json'), encoding='utf-8'))


def targets(coll0):
    """coll[0] 里需要在例句中出现的实词。斜杠给的是可选项，任一即可。"""
    s = TAGS.sub(' ', coll0)
    s = s.replace('-', ' ').replace('.', ' ')
    out = []
    for tok in s.split():
        tok = tok.strip('.,;:!?()[]"\'')
        if not tok:
            continue
        alts = [a.strip("'").lower() for a in tok.split('/') if a.strip("'")]
        alts = [a for a in alts if a and a not in STOP and a not in JUNK and not a.isdigit()]
        if alts:
            out.append(alts)
    return out


def stem(w):
    w = w.lower().strip('.,;:!?()[]"\u2019\'')
    w = w.rstrip("'")
    if w.endswith("'s"):
        w = w[:-2]
    for suf in ('ing', 'ied', 'ies', 'ed', 'es', 's', 'd'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def lev1(a, b, k=1):
    """编辑距离 <= k（容 OCR 的字符错）"""
    la, lb = len(a), len(b)
    if abs(la - lb) > k:
        return False
    if k > 1:
        prev = list(range(lb + 1))
        for i in range(1, la + 1):
            cur = [i] + [0] * lb
            for j in range(1, lb + 1):
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                             prev[j - 1] + (a[i - 1] != b[j - 1]))
            prev = cur
        return prev[lb] <= k
    i = j = 0
    diff = 0
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        diff += 1
        if diff > 1:
            return False
        if la > lb:
            i += 1
        elif lb > la:
            j += 1
        else:
            i += 1
            j += 1
    return diff + (la - i) + (lb - j) <= 1


def matches(word, target):
    if word == target:
        return True
    if len(target) >= 3 and lev1(word, target):
        return True
    if len(target) >= 5 and len(word) >= 6 and lev1(word, target, 2):
        return True
    a, b = stem(word), stem(target)
    if a == b:
        return True
    # 处理 double consonant / -y 变化：plan->planned, carry->carried
    if len(a) >= 3 and len(b) >= 3:
        if a.startswith(b) and len(a) - len(b) <= 2:
            return True
        if b.startswith(a) and len(b) - len(a) <= 2:
            return True
        if a[:-1] == b or b[:-1] == a:
            return True
        # OCR 掉了首字母：atest <- latest
        if len(b) >= 4 and a.endswith(b) and len(a) - len(b) <= 2:
            return True
        if len(a) >= 4 and b.endswith(a) and len(b) - len(a) <= 2:
            return True
    return False


def check(en, coll0):
    raw = [w.strip('.,;:!?()[]"\u201c\u201d') for w in re.split(r'[\s\u2014\u2013]+', en.lower()) if w]
    words = []
    for w in raw:
        words.append(w)
        if '-' in w:
            words.append(w.replace('-', ''))
            words.extend(p for p in w.split('-') if p)
    # 相邻词拼接，兜 OCR 把两个词粘一起的情况（and run -> andrun）
    flat = [p for w in raw for p in (w.split('-') if '-' in w else [w]) if p]
    for i in range(len(flat) - 1):
        words.append(flat[i] + flat[i + 1])
        if i + 2 < len(flat):
            words.append(flat[i] + flat[i + 1] + flat[i + 2])
    missing = []
    for alts in targets(coll0):
        if not any(matches(w, t) for w in words for t in alts):
            missing.append('/'.join(alts))
    return missing


def cmd_show(batch, start=0, count=300):
    data = load(batch)
    start, count = int(start), int(count)
    for i, x in enumerate(data):
        if i < start or i >= start + count:
            continue
        cn = (x.get('cn') or '').replace('\n', ' ')[:30]
        print('%d\t%s\t[%s %s]\t%s' % (i + 1, x['coll'][0], x['word'], x['pos'], cn))


def cmd_build(batch):
    import glob
    data = load(batch)
    paths = sorted(glob.glob(os.path.join(PARTS, batch + '.p*.txt')))
    rows = {}
    for path in paths:
        for ln, line in enumerate(open(path, encoding='utf-8'), 1):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) != 3:
                print('BADLINE %s:%d: %r' % (os.path.basename(path), ln, line[:80]))
                continue
            idx, en, zh = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if not idx.isdigit():
                print('BADIDX %s:%d: %r' % (os.path.basename(path), ln, line[:80]))
                continue
            rows[int(idx)] = (en, zh)

    missing_idx = [i + 1 for i in range(len(data)) if i + 1 not in rows]
    if missing_idx:
        print('MISSING %d: %s' % (len(missing_idx), missing_idx[:60]))
    extra = [i for i in rows if i < 1 or i > len(data)]
    if extra:
        print('EXTRA %s' % extra[:20])

    bad = []
    ex = []
    for i, x in enumerate(data):
        n = i + 1
        if n not in rows:
            continue
        en, zh = rows[n]
        miss = check(en, x['coll'][0])
        if miss:
            bad.append((n, x['coll'][0], '|'.join(miss), en))
        nw = len(en.split())
        if nw < 8 or nw > 20:
            bad.append((n, x['coll'][0], 'LEN=%d' % nw, en))
        if not zh.endswith(('。', '！', '？')):
            bad.append((n, x['coll'][0], 'ZH_END', zh))
        ex.append({'k': x['k'], 'en': en, 'zh': zh})

    for b in bad:
        print('BAD %d\t%s\tmiss=%s\t%s' % b)
    print('---')
    print('batch=%s n=%d written=%d bad=%d' % (batch, len(data), len(ex), len(bad)))

    if not missing_idx and not bad:
        out = os.path.join(DIR, batch + '.out.json')
        json.dump({'n': len(data), 'ex': ex}, open(out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('WROTE %s' % out)
    else:
        print('NOT WRITTEN (fix first)')


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'show':
        cmd_show(*sys.argv[2:])
    elif c == 'build':
        cmd_build(sys.argv[2])
