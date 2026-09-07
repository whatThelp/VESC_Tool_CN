# -*- coding: utf-8 -*-
"""把译文回填进 XML。只替换可翻译片段所占的那一段字节，其余内容逐字节保留。"""
import re, json, os, sys, hashlib, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import NODE_RE, TEXT_RE, is_translatable, PARAM_RE, SKIP_PARAMS

def load_trans(transdir):
    tr = {}
    for f in sorted(glob.glob(os.path.join(transdir, 'batch*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        for k, v in d.items():
            if k in tr and tr[k] != v:
                print(f'  警告: {k} 在多个批次里译文不同，用后者')
            tr[k] = v
    return tr

def spans_of(src):
    opens = [(m.start(), m.group(1)) for m in PARAM_RE.finditer(src)]
    def owner(pos):
        lo, hi, best = 0, len(opens) - 1, ''
        while lo <= hi:
            mid = (lo + hi) // 2
            if opens[mid][0] <= pos: best = opens[mid][1]; lo = mid + 1
            else: hi = mid - 1
        return best
    out = []
    for m in NODE_RE.finditer(src):
        tag, body, off = m.group(1), m.group(2), m.start(2)
        if owner(m.start()) in SKIP_PARAMS:
            continue
        if tag in ('longName', 'enumNames'):
            if is_translatable(body):
                out.append((off, off + len(body), body))
        else:
            for t in TEXT_RE.finditer(body):
                if is_translatable(t.group(1)):
                    out.append((off + t.start(1), off + t.end(1), t.group(1)))
    return out

def apply_file(path, outpath, tr, stats):
    src = open(path, encoding='utf-8').read()
    spans = spans_of(src)
    buf = src
    for (s, e, txt) in reversed(spans):
        key = hashlib.md5(txt.encode()).hexdigest()[:10]
        stats['total'] += 1
        if key not in tr:
            stats['skipped'] += 1
            stats['skip_samples'].append(txt[:60])
            continue
        lead = txt[:len(txt) - len(txt.lstrip())]
        trail = txt[len(txt.rstrip()):]
        buf = buf[:s] + lead + tr[key].strip() + trail + buf[e:]
        stats['done'] += 1
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    open(outpath, 'w', encoding='utf-8', newline='').write(buf)

if __name__ == '__main__':
    cfgdir, transdir, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    tr = load_trans(transdir)
    print(f'译文条目 {len(tr)}')
    stats = {'total': 0, 'done': 0, 'skipped': 0, 'skip_samples': []}
    for f in ('parameters_mcconf.xml', 'parameters_appconf.xml', 'info.xml'):
        apply_file(os.path.join(cfgdir, f), os.path.join(outdir, f), tr, stats)
    print(f"片段 {stats['total']}，已替换 {stats['done']}，保留原文 {stats['skipped']}"
          f"（覆盖率 {stats['done']/stats['total']*100:.1f}%）")
    seen = []
    for s in stats['skip_samples']:
        if s not in seen: seen.append(s)
    print('保留原文的前 25 种：')
    for s in seen[:25]: print('   ', repr(s))
