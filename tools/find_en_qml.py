# -*- coding: utf-8 -*-
"""列出 QML 文件里仍是英文的字符串字面量（排除 import、资源路径、参数名等）。
用法: python find_en_qml.py <源码根> <相对路径> [...]"""
import re, sys

root = sys.argv[1]
SKIP_LINE = re.compile(r'^\s*import |getParam|updateParam|getEditor|objectName|font\.family|console\.')
LIT = re.compile(r'"((?:[^"\\]|\\.)*)"')
for rel in sys.argv[2:]:
    for i, l in enumerate(open(root + '/' + rel, encoding='utf-8'), 1):
        if SKIP_LINE.search(l):
            continue
        for m in LIT.finditer(l):
            s = m.group(1)
            if not re.search(r'[A-Za-z]{2,}', s):
                continue
            if re.search(r'[一-鿿]', s):
                continue
            if re.match(r'^(qrc:|image://|file:|#)', s) or re.match(r'^[a-z_0-9.]+$', s):
                continue
            print('%s:%d  %r   | %s' % (rel.split('/')[-1], i, s, l.strip()[:100]))
