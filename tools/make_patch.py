# -*- coding: utf-8 -*-
"""生成"只含功能性改动"的源码补丁（相对上游原版源码）。

做法：从上游原版拷出涉及的文件 -> 打旧补丁 -> 依次执行 fixup.py 的 main.cpp / 页面名两项、
fix_detect_zh.py -> 与原版做 diff。这样补丁里只有功能改动，不夹带几千处字符串翻译。
用法: python make_patch.py <上游源码根> <旧补丁> <输出补丁>
"""
import os, sys, shutil, subprocess, difflib, runpy

up, old_patch, out = sys.argv[1:4]
here = os.path.dirname(os.path.abspath(__file__))
work = os.path.join(here, 'patchwork')
shutil.rmtree(work, ignore_errors=True)
FILES = ['main.cpp', 'configparam.h', 'configparams.cpp', 'mainwindow.cpp',
         'utility.h', 'utility.cpp', 'widgets/detectallfocdialog.cpp', 'mobile/SetupWizardFoc.qml']
for side in ('a', 'b'):
    for f in FILES:
        d = os.path.join(work, side, os.path.dirname(f))
        os.makedirs(d, exist_ok=True)
        # 统一成 LF 再处理（上游部分文件是 CRLF），补丁也按 LF 生成
        t = open(os.path.join(up, f), encoding='utf-8', newline='').read().replace('\r\n', '\n')
        open(os.path.join(work, side, f), 'w', encoding='utf-8', newline='\n').write(t)

b = os.path.join(work, 'b')
# 1) 旧补丁：qt_zh_CN 翻译器 + enumNamesSig
r = subprocess.run(['patch', '-p1', '-d', b, '-i', os.path.abspath(old_patch)],
                   capture_output=True, text=True)
print(r.stdout.strip())
assert r.returncode == 0, r.stderr

# 2) fixup.py 里的两项功能改动（vesc_cn_extra 翻译器、页面名成对替换）
g = {'__name__': 'fixup_part'}
src = open(os.path.join(here, 'fixup.py'), encoding='utf-8').read()
start = src.index('# ---------- 2. 页面名成对替换 ----------')
end = src.index('# ---------- 3. 配置检查标题 ----------')
s5 = src.index('# ---------- 5. main.cpp 加载 vesc_cn_extra.qm ----------')
e5 = src.index('# ---------- 6. 连接页 TCP/UDP 服务端列表的标题 ----------')
code = ('import os\nroot = %r\nlog = []\n' % b +
        src[src.index('def rw('):src.index('# ---------- 1. 位域 Unused ----------')] +
        src[start:end] + src[s5:e5])
exec(compile(code, 'fixup_part', 'exec'), g)
print('\n'.join(g['log']))

# 3) 检测结果中文显示
sys.argv = ['fix_detect_zh.py', b]
runpy.run_path(os.path.join(here, 'fix_detect_zh.py'), run_name='__main__')

# 4) 生成统一 diff（按 LF 比较，输出 LF）
HEADER = """# 汉化版对 VESC Tool 源码做的功能性改动（相对上游 master dc53c658；其余改动全部是字符串替换）
# 1. main.cpp        : 装载 Qt 自带简体中文翻译 qt_zh_CN.qm，以及本项目的补充翻译 vesc_cn_extra.qm
#                      （Qt 5.15 的 qt_zh_CN.qm 缺 QPlatformTheme 上下文，确定/取消/是/否 靠后者补上）
# 2. configparam.h   : 新增 enumNamesSig 字段（enumNames 的英文原名）
# 3. configparams.cpp: 解析 enumNamesSig；配置签名改用英文原名计算
#    —— 第 2、3 条是必须的：签名把 enumNames 算进去，翻译下拉选项会让签名
#       和固件端对不上，导致读写配置被判 Invalid signature。
# 4. mainwindow.cpp  : Terminal / QML Scripting / LispBM Scripting 三个页面名在
#                      addPageItem() 和 showPage() 两侧成对替换（页面名同时是跳转用的键）
# 5. utility.h/.cpp  : 新增 Utility::detectResultZh()，把 FOC 检测结果翻成中文
#    widgets/detectallfocdialog.cpp、mobile/SetupWizardFoc.qml：只在显示处调用它，
#    判断成败仍用英文原文 startsWith("Success!")
#
# 用法（在上游源码根目录）: patch -p1 < source_patches.diff

"""
parts = [HEADER]
for f in FILES:
    a_txt = open(os.path.join(work, 'a', f), encoding='utf-8', newline='').read().replace('\r\n', '\n')
    b_txt = open(os.path.join(work, 'b', f), encoding='utf-8', newline='').read().replace('\r\n', '\n')
    if a_txt == b_txt:
        continue
    d = difflib.unified_diff(a_txt.splitlines(True), b_txt.splitlines(True),
                             'a/' + f, 'b/' + f, n=3)
    parts.append(''.join(d) + '\n')
open(out, 'w', encoding='utf-8', newline='\n').write(''.join(parts))
print('写出', out)

# 5) 自检：把补丁打回一份干净的原版上，结果应与 b 完全一致
chk = os.path.join(work, 'check')
shutil.copytree(os.path.join(work, 'a'), chk)
r = subprocess.run(['patch', '-p1', '-d', chk, '-i', os.path.abspath(out)],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
for f in FILES:
    x = open(os.path.join(chk, f), encoding='utf-8', newline='').read().replace('\r\n', '\n')
    y = open(os.path.join(b, f), encoding='utf-8', newline='').read().replace('\r\n', '\n')
    assert x == y, '自检失败: ' + f
print('自检通过：补丁可干净地打在原版上')
