# -*- coding: utf-8 -*-
"""在重放出的源码树上做修正（全部是逐字节的定点替换，不重排文件）：

1. [BUG] 位域参数(type=6)里的 enumNames "未使用" 还原为 "Unused"
   —— parameditbitfield.cpp / ParamEditBitfield.qml 用 text().toLower() != "unused"
   决定是否隐藏保留位，翻译后隐藏失效。下拉型(type=4)的"未使用"是正常显示的选项，不动。
2. mainwindow.cpp 三个页面名在 addPageItem()/showPage() 两侧成对替换
3. vescinterface.cpp 配置检查提示的三个 <b>标题</b>
4. .ui 里 "加载 XML" 统一为发布版用的 "载入 XML"（与 QML 一致）
5. main.cpp 加载本项目的补充翻译 vesc_cn_extra.qm（标准按钮 确定/取消/是/否）
6. 连接页 TCP/UDP 服务端列表的两个标题
7. .ui 数值框的描述性前缀（端口：/ 波特率：/ 最大功率损耗：等）

全部可重复执行。用法: python fixup.py <源码根> [额外的config目录 ...]
"""
import re, os, sys

root = sys.argv[1]
extra_cfg = sys.argv[2:]
log = []


def rw(path, fn):
    src = open(path, encoding='utf-8', newline='').read()
    new = fn(src)
    if new != src:
        open(path, 'w', encoding='utf-8', newline='').write(new)
    return new != src


# ---------- 1. 位域 Unused ----------
UNUSED = '<enumNames>未使用</enumNames>'
TYPE_RE = re.compile(r'<type>(\d+)</type>')


def fix_bitfield(src):
    out, last, n = [], 0, 0
    for m in re.finditer(re.escape(UNUSED), src):
        types = list(TYPE_RE.finditer(src, 0, m.start()))
        if types and types[-1].group(1) == '6':
            out.append(src[last:m.start()])
            out.append('<enumNames>Unused</enumNames>')
            last = m.end()
            n += 1
    out.append(src[last:])
    fix_bitfield.count += n
    return ''.join(out)


cfg_dirs = [os.path.join(root, 'res', 'config', v) for v in ('6.06', '7.00', '7.01')] + extra_cfg
for d in cfg_dirs:
    for f in ('parameters_mcconf.xml', 'parameters_appconf.xml'):
        p = os.path.join(d, f)
        if not os.path.exists(p):
            continue
        fix_bitfield.count = 0
        rw(p, fix_bitfield)
        log.append('位域 Unused 还原 %2d 处  %s' % (fix_bitfield.count, os.path.relpath(p, os.path.dirname(root))))

# ---------- 2. 页面名成对替换 ----------
PAGES = {'Terminal': '终端', 'QML Scripting': 'QML 脚本', 'LispBM Scripting': 'LispBM 脚本'}


def fix_pages(src):
    n = 0
    for en, zh in PAGES.items():
        for call in ('addPageItem(', 'showPage('):
            pat = call + '"' + en + '"'
            n += src.count(pat)
            src = src.replace(pat, call + '"' + zh + '"')
    fix_pages.count = n
    return src


rw(os.path.join(root, 'mainwindow.cpp'), fix_pages)
log.append('页面名 addPageItem/showPage 成对替换 %d 处' % fix_pages.count)

# ---------- 3. 配置检查标题 ----------
HEADS = {'<b>Current Checks</b><br>': '<b>电流检查</b><br>',
         '<b>Limit Checks</b><br>': '<b>限值检查</b><br>',
         '<b>Overmodulation Check</b><br>': '<b>过调制检查</b><br>'}


def fix_heads(src):
    n = 0
    for en, zh in HEADS.items():
        n += src.count(en)
        src = src.replace(en, zh)
    fix_heads.count = n
    return src


rw(os.path.join(root, 'vescinterface.cpp'), fix_heads)
log.append('配置检查标题 %d 处' % fix_heads.count)

# ---------- 4. 载入 XML ----------
tot = 0
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d not in ('build', '.git')]
    for f in fn:
        if f.endswith('.ui'):
            p = os.path.join(dp, f)
            c = open(p, encoding='utf-8').read().count('<string>加载 XML</string>')
            if c:
                rw(p, lambda s: s.replace('<string>加载 XML</string>', '<string>载入 XML</string>'))
                tot += c
log.append('.ui 中 加载 XML -> 载入 XML %d 处' % tot)

# ---------- 5. main.cpp 加载 vesc_cn_extra.qm ----------
# 发布版 exe 有这段、仓库里的补丁漏了。qt_zh_CN.qm 缺 QPlatformTheme 上下文，
# 标准按钮（OK/Cancel/Yes/No）要靠这个自制的补充翻译。
EXTRA_OLD = """                a->installTranslator(&qtTranslator);
            }
        }"""
EXTRA_NEW = """                a->installTranslator(&qtTranslator);
            }
            // Qt 5.15 的 qt_zh_CN.qm 没有 QPlatformTheme 上下文，标准按钮（OK/Cancel/Yes/No）
            // 仍是英文，由本项目自制的 vesc_cn_extra.qm 补上。后装的翻译器优先。
            static QTranslator extraTranslator;
            if (extraTranslator.load("vesc_cn_extra", appTs)) {
                a->installTranslator(&extraTranslator);
            }
        }"""


def fix_extra(src):
    if 'vesc_cn_extra' in src:
        fix_extra.count = 0
        return src
    nl = '\r\n' if '\r\n' in src else '\n'
    old, new = EXTRA_OLD.replace('\n', nl), EXTRA_NEW.replace('\n', nl)
    fix_extra.count = src.count(old)
    return src.replace(old, new, 1)


rw(os.path.join(root, 'main.cpp'), fix_extra)
log.append('main.cpp 加载 vesc_cn_extra.qm %d 处' % fix_extra.count)

# ---------- 6. 连接页 TCP/UDP 服务端列表的标题 ----------
CONN = {'"Server IPs\\n"': '"服务端 IP\\n"', '"Connected Clients\\n"': '"已连接的客户端\\n"'}


def fix_conn(src):
    n = 0
    for en, zh in CONN.items():
        n += src.count(en)
        src = src.replace(en, zh)
    fix_conn.count = n
    return src


rw(os.path.join(root, 'pages', 'pageconnection.cpp'), fix_conn)
log.append('pageconnection.cpp 服务端列表标题 %d 处' % fix_conn.count)

# ---------- 7. .ui 数值框的描述性前缀 ----------
# 只翻由英文单词组成的描述性前缀；W: / KP: / λ: / Lq-Ld: / 0x 地址这类符号型前缀保持原样。
PREFIX = {
    'Port: ': '端口：', 'TCP Port: ': 'TCP 端口：', 'UDP Port: ': 'UDP 端口：',
    'Baud: ': '波特率：', 'Bit rate: ': '比特率：',
    'Min: ': '最小：', 'Max: ': '最大：', 'To: ': '至：', 'From: ': '从：',
    'Step: ': '步长：', 'Scale: ': '缩放：', 'Ratio: ': '比值：', 'Offset: ': '偏置：',
    'Value: ': '值：', 'Time: ': '时间：', 'Center: ': '中位：', 'End: ': '结束：',
    'History: ': '历史：', 'Plot Points: ': '绘图点数：', 'Sample Interval: ': '采样间隔：',
    'Preview Scale: ': '预览缩放：', 'Load Color Scale: ': '负载色阶：', 'Pos Now: ': '当前位置：',
    'Temp Increase: ': '温升：', 'Motors: ': '电机数：', 'Max RPM: ': '最高转速：',
    'Gearing: ': '传动比：', 'Gear Eff: ': '传动效率：', 'Pwr: ': '功率：',
    'Motor Pulley: ': '电机端齿数：', 'Wheel Pulley: ': '轮端齿数：',
    'Max Power Loss: ': '最大功率损耗：',
    'Current In Min: ': '最小输入电流：', 'Current In Max: ': '最大输入电流：',
    'Min Current: ': '最小电流：', 'Max Current: ': '最大电流：',
    'Openloop ERPM: ': '开环电气转速：', 'Sensorless ERPM: ': '无感电气转速：',
    'Min ERPM: ': '最小电气转速：', 'Max ERPM: ': '最大电气转速：',
    'Observer Gain (x1M): ': '观测器增益（×1M）：',
}
PREFIX_RE = re.compile(r'(<property name="prefix">\s*<string>)([^<]*)(</string>)')
ptot = 0
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d not in ('build', '.git')]
    for f in fn:
        if not f.endswith('.ui'):
            continue
        p = os.path.join(dp, f)

        def sub(m):
            global ptot
            zh = PREFIX.get(m.group(2))
            if zh is None:
                return m.group(0)
            ptot += 1
            return m.group(1) + zh + m.group(3)
        rw(p, lambda s: PREFIX_RE.sub(sub, s))
log.append('.ui 数值框前缀 %d 处' % ptot)

print('\n'.join(log))
