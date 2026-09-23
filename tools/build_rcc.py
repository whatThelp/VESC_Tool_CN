# -*- coding: utf-8 -*-
"""打包给官方原版 VESC Tool 用的外挂配置资源包 res_config_cn_for_official.rcc。

官方 exe 启动时会注册 %APPDATA%\\VESC\\VESC Tool\\res_config.rcc，并优先使用其中
/res/config_download/ 下修改时间更新的文件。只要缺了某个版本目录，连接该版本固件时就会找不到
配置，所以包里必须带齐上游 res/config 的全部版本 + fw.xml，只把 6.06/7.00/7.01 换成中文版。

用法: python build_rcc.py <上游 res/config 目录> <config_cn_official 目录> <rcc.exe> <输出 .rcc>
"""
import os, sys, shutil, subprocess, tempfile

up_cfg, cn_cfg, rcc, out = sys.argv[1:5]
stage = tempfile.mkdtemp(prefix='rcc_stage_')
dl = os.path.join(stage, 'res', 'config_download')
os.makedirs(dl)

files = []
for name in sorted(os.listdir(up_cfg)):
    src = os.path.join(up_cfg, name)
    if os.path.isdir(src):
        use = os.path.join(cn_cfg, name) if os.path.isdir(os.path.join(cn_cfg, name)) else src
        os.makedirs(os.path.join(dl, name))
        for f in sorted(os.listdir(src)):
            s = os.path.join(use, f) if os.path.exists(os.path.join(use, f)) else os.path.join(src, f)
            shutil.copyfile(s, os.path.join(dl, name, f))   # copyfile 不保留时间戳：文件时间=打包时间
            files.append('res/config_download/%s/%s' % (name, f))
    elif name == 'fw.xml':
        shutil.copyfile(src, os.path.join(dl, name))
        files.append('res/config_download/fw.xml')

qrc = os.path.join(stage, 'res_config.qrc')
with open(qrc, 'w', encoding='utf-8') as q:
    q.write('<RCC>\n    <qresource prefix="/">\n')
    for f in files:
        q.write('        <file>%s</file>\n' % f)
    q.write('    </qresource>\n</RCC>\n')

subprocess.run([rcc, '-binary', qrc, '-o', os.path.abspath(out)], check=True, cwd=stage)
print('qrc 条目 %d，写出 %s（%d 字节）' % (len(files), out, os.path.getsize(out)))
shutil.rmtree(stage, ignore_errors=True)
