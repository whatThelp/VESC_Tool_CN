# -*- coding: utf-8 -*-
"""第二阶段回填：按 index.json 记录的绝对偏移，逐段替换 .ui / .qml / .cpp 里的文本。

倒序替换以保证偏移有效；原文的前后空白自动保留（很多 QML/C++ 字符串靠尾部空格
和下一段拼接，丢了就会粘连）。
"""
import json, os, sys, glob, hashlib


def load_trans(*dirs):
    tr = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, '*.json'))):
            for k, v in json.load(open(f, encoding='utf-8')).items():
                tr[k] = v
    return tr


def main():
    root = sys.argv[1]
    workdirs = sys.argv[2].split(',')
    tr = load_trans(*[os.path.join(w, 'trans') for w in workdirs])
    print('译文词典 %d 条' % len(tr))

    total = done = skipped = 0
    skips = []
    for w in workdirs:
        index = json.load(open(os.path.join(w, 'index.json'), encoding='utf-8'))
        for rel, items in index.items():
            path = os.path.join(root, rel)
            src = open(path, encoding='utf-8').read()
            buf, changed = src, 0
            for it in sorted(items, key=lambda i: -i['start']):
                total += 1
                txt = it['text']
                # 偏移必须仍然对得上，否则说明文件被改过，直接放弃这一段
                if buf[it['start']:it['end']] != txt:
                    skipped += 1
                    skips.append('%s: 偏移不匹配 %r' % (rel, txt[:40]))
                    continue
                key = hashlib.md5(txt.encode()).hexdigest()[:10]
                if key not in tr:
                    skipped += 1
                    skips.append('%s: 未译 %r' % (rel, txt[:40]))
                    continue
                lead = txt[:len(txt) - len(txt.lstrip())]
                trail = txt[len(txt.rstrip()):]
                buf = buf[:it['start']] + lead + tr[key].strip() + trail + buf[it['end']:]
                done += 1
                changed += 1
            if changed:
                open(path, 'w', encoding='utf-8', newline='').write(buf)
    print('片段 %d，已替换 %d，保留原文 %d（覆盖率 %.1f%%）'
          % (total, done, skipped, done / total * 100))
    seen = []
    for s in skips:
        if s not in seen:
            seen.append(s)
    for s in seen[:30]:
        print('   ', s)


if __name__ == '__main__':
    main()
