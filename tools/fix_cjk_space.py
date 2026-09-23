# -*- coding: utf-8 -*-
"""去掉中文字符串拼接处多余的空格。

英文原文靠 "... word " + "word ..." 这种尾部空格把两段拼成一句；翻成中文后保留了
尾部空格，界面上就成了"请确认 周围没有……"。这里只处理一种情况：
    某段字面量以【中文字符或中文标点 + 一个或多个空格】结尾，
    且紧跟的下一段字面量（中间只隔 + / 换行 / 空白）以中文字符或中文标点开头。
此时删掉那些空格。中英文之间的空格（如 "VESC 的"）不在拼接处，不受影响。
用法: python fix_cjk_space.py <源码根>        # 直接修改
      python fix_cjk_space.py <源码根> --dry  # 只列出
"""
import os, re, sys

root = sys.argv[1]
dry = '--dry' in sys.argv
CJK = '　-〿一-鿿＀-￯'
# 段尾：中文 + 空格 + 引号；段间：空白、可选的 +（QML/JS）；下一段开头：引号 + 中文
PAT = re.compile(r'([' + CJK + r'])( +)"(\s*\+?\s*)"(?=[' + CJK + r'])')
tot = 0
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d not in ('build', '.git')]
    for f in fn:
        if not f.endswith(('.cpp', '.h', '.qml', '.js')):
            continue
        p = os.path.join(dp, f)
        s = open(p, encoding='utf-8', newline='').read()
        hits = list(PAT.finditer(s))
        if not hits:
            continue
        for m in hits:
            line = s.count('\n', 0, m.start()) + 1
            print('%s:%d  %r' % (os.path.relpath(p, root), line, s[m.start() - 12:m.end() + 8]))
        tot += len(hits)
        if not dry:
            open(p, 'w', encoding='utf-8', newline='').write(PAT.sub(r'\1"\3"', s))
print('共 %d 处%s' % (tot, '（未修改）' if dry else '，已修改'))
