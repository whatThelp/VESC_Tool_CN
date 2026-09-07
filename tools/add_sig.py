# -*- coding: utf-8 -*-
"""给汉化后的配置 XML 补上 <enumNamesSig>（enumNames 的英文原名）。

配置签名 ConfigParams::getSignature() 把 enumNames 算进去，而固件端的签名常量是按
英文 XML 生成的。翻译了下拉选项就会让签名对不上，读写配置直接被判 Invalid signature。
补上英文原名后，打了补丁的 VESC Tool 用它算签名，界面照样显示中文。
"""
import re, sys, os
import xml.etree.ElementTree as ET

ENUM_LINE = re.compile(r'(?m)^([ \t]*)<enumNames>(.*?)</enumNames>[ \t]*\r?\n')


def enum_runs(src):
    """把文件里连续的一组 <enumNames> 归为一段，返回 [(插入位置, 缩进, 条数)]"""
    ms = list(ENUM_LINE.finditer(src))
    runs, cur = [], []
    for m in ms:
        if cur and cur[-1].end() != m.start():
            runs.append(cur)
            cur = []
        cur.append(m)
    if cur:
        runs.append(cur)
    return [(r[-1].end(), r[0].group(1), len(r)) for r in runs]


def orig_enum_lists(path):
    """原版 XML 里按文档顺序、每个带 enumNames 的参数的英文名列表"""
    root = ET.parse(path).getroot()
    out = []
    for sec in root:
        for p in sec:
            names = [e.text or '' for e in p.findall('enumNames')]
            if names:
                out.append((p.tag, names))
    return out


def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def process(orig_path, zh_path):
    src = open(zh_path, encoding='utf-8').read()
    if '<enumNamesSig>' in src:
        return 'already', 0
    runs = enum_runs(src)
    lists = orig_enum_lists(orig_path)
    if len(runs) != len(lists):
        return 'MISMATCH runs=%d params=%d' % (len(runs), len(lists)), 0
    for (pos, indent, n), (tag, names) in zip(runs, lists):
        if n != len(names):
            return 'MISMATCH %s: %d vs %d' % (tag, n, len(names)), 0
    # 从后往前插，保证偏移有效
    added = 0
    for (pos, indent, n), (tag, names) in reversed(list(zip(runs, lists))):
        block = ''.join('%s<enumNamesSig>%s</enumNamesSig>\n' % (indent, esc(x)) for x in names)
        src = src[:pos] + block + src[pos:]
        added += n
    open(zh_path, 'w', encoding='utf-8', newline='').write(src)
    return 'ok', added


if __name__ == '__main__':
    origdir, zhdir = sys.argv[1], sys.argv[2]
    for f in ('parameters_mcconf.xml', 'parameters_appconf.xml', 'info.xml'):
        st, n = process(os.path.join(origdir, f), os.path.join(zhdir, f))
        print('  %-26s %s (%d 条)' % (f, st, n))
