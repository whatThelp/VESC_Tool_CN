# -*- coding: utf-8 -*-
"""按首次出现顺序把去重片段切成批次文件，同一条 description 的多个片段尽量相邻。"""
import json, os, sys, hashlib
outdir = sys.argv[1]; budget = int(sys.argv[2])
index = json.load(open(os.path.join(outdir, 'index.json'), encoding='utf-8'))
seen, ordered = set(), []
for f in ('parameters_mcconf.xml', 'parameters_appconf.xml', 'info.xml'):
    for it in index[f]:
        t = it['text']
        if t in seen: continue
        seen.add(t)
        ordered.append({'id': hashlib.md5(t.encode()).hexdigest()[:10],
                        'file': f.replace('parameters_', '').replace('.xml', ''),
                        'param': it['param'], 'tag': it['tag'], 'text': t})
bd = os.path.join(outdir, 'batches'); os.makedirs(bd, exist_ok=True)
batch, size, n = [], 0, 0
def flush(batch, n):
    if not batch: return
    with open(os.path.join(bd, f'batch{n:02d}.txt'), 'w', encoding='utf-8') as fh:
        for it in batch:
            fh.write(f"{it['id']}\t{it['file']}:{it['param']}\t{it['tag']}\t"
                     f"{it['text'].replace(chr(92), chr(92)*2).replace(chr(10), '\n')}\n")
for it in ordered:
    L = len(it['text'])
    if size + L > budget and batch:
        n += 1; flush(batch, n); batch, size = [], 0
    batch.append(it); size += L
n += 1; flush(batch, n)
print(f'{len(ordered)} 条 -> {n} 个批次')
for i in range(1, n+1):
    p = os.path.join(bd, f'batch{i:02d}.txt')
    print(f'  batch{i:02d}: {sum(1 for _ in open(p,encoding="utf-8"))} 行, {os.path.getsize(p)} B')
