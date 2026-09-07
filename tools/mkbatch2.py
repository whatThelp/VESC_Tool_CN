# -*- coding: utf-8 -*-
"""把第二阶段的去重片段切成批次文件（segments.json 已按首次出现顺序排好）。"""
import json, os, sys

outdir, budget, prefix = sys.argv[1], int(sys.argv[2]), sys.argv[3]
segs = json.load(open(os.path.join(outdir, 'segments.json'), encoding='utf-8'))
bd = os.path.join(outdir, 'batches')
os.makedirs(bd, exist_ok=True)

batch, size, n = [], 0, 0


def flush(batch, n):
    if not batch:
        return
    with open(os.path.join(bd, '%s%02d.txt' % (prefix, n)), 'w', encoding='utf-8') as fh:
        for it in batch:
            t = it['text'].replace('\\', '\\\\').replace('\n', '\\n')
            fh.write('%s\t%s\t%s\t%s\n' % (it['id'], it['file'], it['prop'], t))


for it in segs:
    L = len(it['text']) + 40          # 加上 file/prop 那一列的开销
    if size + L > budget and batch:
        n += 1
        flush(batch, n)
        batch, size = [], 0
    batch.append(it)
    size += L
n += 1
flush(batch, n)
print('%d 条 -> %d 个批次' % (len(segs), n))
for i in range(1, n + 1):
    p = os.path.join(bd, '%s%02d.txt' % (prefix, i))
    print('  %s%02d: %d 行, %d B' % (prefix, i, sum(1 for _ in open(p, encoding='utf-8')),
                                     os.path.getsize(p)))
