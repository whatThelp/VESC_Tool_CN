# -*- coding: utf-8 -*-
"""结构校验：译后 XML 必须与原版结构完全一致，只有可翻译文本不同。"""
import xml.etree.ElementTree as ET
import re, sys, os

TRANSLATABLE = ('longName', 'description', 'enumNames')
TAG_RE = re.compile(r'&lt;[^&]*?&gt;')

def signature(path):
    root = ET.parse(path).getroot()
    sig = []
    for params in root:
        for p in params:
            item = [p.tag]
            for child in p:
                if child.tag == 'enumNamesSig':   # 汉化版新增，结构对比时忽略
                    continue
                if child.tag in TRANSLATABLE:
                    item.append(child.tag)
                else:
                    item.append(f'{child.tag}={child.text}')
            sig.append(tuple(item))
    return sig

DESC_RE = re.compile(r'<description>(.*?)</description>', re.S)
PARAM_LINE = re.compile(r'^[ 	]*<([A-Za-z_][A-Za-z0-9_.]*)>[ 	]*$', re.M)

def html_skeleton(path):
    """每个 description 里 HTML 标签的序列，在原始文件文本上比对（不做 XML 反转义），
    这样 &amp;lt; 这类双重转义不会被误认成标签。"""
    src = open(path, encoding='utf-8').read()
    opens = [(m.start(), m.group(1)) for m in PARAM_LINE.finditer(src)]
    def owner(pos):
        lo, hi, best = 0, len(opens) - 1, ''
        while lo <= hi:
            mid = (lo + hi) // 2
            if opens[mid][0] <= pos: best = opens[mid][1]; lo = mid + 1
            else: hi = mid - 1
        return best
    return [(owner(m.start()), tuple(TAG_RE.findall(m.group(1))))
            for m in DESC_RE.finditer(src)]

def enum_counts(path):
    root = ET.parse(path).getroot()
    return [(p.tag, sum(1 for c in p if c.tag == 'enumNames'))
            for params in root for p in params]


def enum_sig_names(path, tag):
    """每个参数的 enumNames / enumNamesSig 文本列表"""
    root = ET.parse(path).getroot()
    return [(p.tag, [c.text or '' for c in p if c.tag == tag])
            for params in root for p in params]

ok_all = True
orig, zh = sys.argv[1], sys.argv[2]
for f in ('parameters_mcconf.xml', 'parameters_appconf.xml', 'info.xml'):
    a, b = os.path.join(orig, f), os.path.join(zh, f)
    raw = open(b, 'rb').read()
    try:
        raw.decode('utf-8')
        enc_ok = True
    except UnicodeDecodeError:
        enc_ok = False
    sa, sb = signature(a), signature(b)
    ha, hb = html_skeleton(a), html_skeleton(b)
    ea, eb = enum_counts(a), enum_counts(b)
    problems = []
    if not enc_ok: problems.append('不是合法 UTF-8')
    if sa != sb:
        problems.append(f'结构指纹不一致（原 {len(sa)} / 译 {len(sb)}）')
        for x, y in zip(sa, sb):
            if x != y: problems.append(f'  首个差异: {x} != {y}'); break
    if ha != hb:
        problems.append('description 的 HTML 标签序列不一致')
        for x, y in zip(ha, hb):
            if x != y: problems.append(f'  首个差异 @{x[0]}'); break
    if ea != eb: problems.append('enumNames 数量/顺序不一致')
    # 配置签名检查。两种交付变体：
    #   带 <enumNamesSig> 的（配汉化版 exe，下拉选项是中文）——签名用 enumNamesSig
    #   不带的（配官方原版 exe）——签名用 enumNames，因此 enumNames 必须保持英文原文
    has_sig = '<enumNamesSig>' in open(b, encoding='utf-8').read()
    sa = enum_sig_names(a, 'enumNames')
    sb = enum_sig_names(b, 'enumNamesSig' if has_sig else 'enumNames')
    kind = 'enumNamesSig' if has_sig else 'enumNames(英文原文)'
    if sa != sb:
        problems.append('%s 与原版 enumNames 不一致（会导致配置签名对不上）' % kind)
        for x, y in zip(sa, sb):
            if x != y: problems.append('  首个差异 @%s: %r != %r' % (x[0], x[1], y[1])); break
    else:
        note = '中文下拉+enumNamesSig' if has_sig else '英文下拉，兼容官方 exe'
        problems.append('__OK__' + note)
    notes = [x[6:] for x in problems if x.startswith('__OK__')]
    problems = [x for x in problems if not x.startswith('__OK__')]
    if problems:
        ok_all = False
        print(f'{f}: 失败')
        for p in problems: print('   ', p)
    else:
        print(f'{f}: OK  （参数 {len(signature(a))} 项，description {len(ha)} 条，'
              f'可解析、UTF-8 合法，签名基准 {notes[0] if notes else "?"}）')
print('全部通过' if ok_all else '存在问题')
sys.exit(0 if ok_all else 1)
