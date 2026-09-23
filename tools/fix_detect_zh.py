# -*- coding: utf-8 -*-
"""检测结果的中文显示。

Utility::detectAllFoc() 返回的英文文本同时承担"逻辑判断"（startsWith("Success!")）和
"显示给用户"两个角色。判断必须用英文原文，所以这里新增 Utility::detectResultZh()，
只在显示的地方把文本翻成中文：
  * widgets/detectallfocdialog.cpp  简易 FOC 检测对话框
  * mobile/SetupWizardFoc.qml        QML 多页 FOC 向导
可重复执行：源码里已有旧版 detectResultZh 时整段替换成当前的表。
用法: python fix_detect_zh.py <源码根>
"""
import os, sys

root = sys.argv[1]


def patch(rel, old, new, count=1):
    p = os.path.join(root, rel)
    src = open(p, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in src else '\n'
    o, n = old.replace('\n', nl), new.replace('\n', nl)
    if n in src:
        print('已存在，跳过:', rel)
        return
    c = src.count(o)
    assert c == count, '%s: 期望 %d 处，实际 %d 处: %r' % (rel, count, c, old[:60])
    open(p, 'w', encoding='utf-8', newline='').write(src.replace(o, n))
    print('已修改:', rel)


# ---------------- utility.h：声明 ----------------
patch('utility.h',
      '    Q_INVOKABLE static QString detectAllFoc(VescInterface *vesc,',
      '    // 汉化版：把 detectAllFoc() 的结果文本翻成中文，仅用于显示（判断成败仍用英文原文）\n'
      '    Q_INVOKABLE static QString detectResultZh(QString res);\n'
      '    Q_INVOKABLE static QString detectAllFoc(VescInterface *vesc,')

# ---------------- utility.cpp：实现 ----------------
TABLE = [
    # 结果表头：去掉英文原文里用来对齐的空格，改成紧凑的"标签：值"。
    # 中文字符的宽度在等宽字体和比例字体里都不是英文的整两倍，补空格对不齐，干脆不对齐。
    ('VESC ID            : ', 'VESC ID：'),
    ('Motor current      : ', '电机电流上限：'),
    ('Motor R            : ', '电机电阻 R：'),
    ('Motor L            : ', '电机电感 L：'),
    ('Motor Lq-Ld        : ', '电感差 Lq-Ld：'),
    ('Motor Flux Linkage : ', '磁链 λ：'),
    ('Temp Comp          : ', '温度补偿：'),
    ('Sensors            : ', '传感器：'),
    ('：True', '：是'), ('：False', '：否'),
    ('：Hall Sensors', '：霍尔传感器'), ('：Sensorless', '：无感'), ('：Encoder', '：编码器'),
    ('Success!', '检测成功！'),
    ('VESCs on CAN-bus:', 'CAN 总线上的 VESC：'),
    ('Detection failed. Reason:', '检测失败，原因：'),
    ('Detection timed out.', '检测超时。'),
    ('VESC disconnected during detection.', '检测过程中 VESC 断开了连接。'),
    # 失败原因（与 Utility::detectAllFoc 中的 switch 一一对应）
    ('Persistent fault, check realtime data page', '存在持续性故障，请到实时数据页查看'),
    ('Flux linkage detection failed', '磁链检测失败'),
    ('CAN detection timeout', 'CAN 检测超时'),
    ('CAN detection failed', 'CAN 检测失败'),
    ('No fault, detection failed for an unknown reason', '没有故障码，检测因未知原因失败'),
    ('Over voltage fault, check voltage is below set limit', '过压故障：请确认电压低于设定的上限'),
    ('Under voltage fault, check voltage is above set limit. If using a power supply make sure the current limit is high enough.',
     '欠压故障：请确认电压高于设定的下限。如果用的是稳压电源，请确认它的限流值足够大。'),
    ('DRV fault, hardware fault occured. Check there are no shorts', 'DRV 故障：发生了硬件故障，请检查有无短路'),
    ('Overcurrent fault, Check there are no shorts and ABS Overcurrent limit is sensible',
     '过流故障：请检查有无短路，以及绝对最大电流设置是否合理'),
    ('Mosfet Overtemperature fault, Mosfets overheated, check for shorts. Cool down device',
     'MOSFET 过温故障：MOSFET 过热，请检查有无短路并让设备降温'),
    ('Motor Overtemperature fault, Motor overheated, is the current limit OK?',
     '电机过温故障：电机过热，请检查电流限值是否合适'),
    ('Gate Driver over voltage, check for hardware failure', '栅极驱动过压：请检查硬件故障'),
    ('Gate Driver under voltage, check for hardware failure', '栅极驱动欠压：请检查硬件故障'),
    ('MCU under voltage, check for hardware failure, shorts on outputs', 'MCU 欠压：请检查硬件故障以及输出端是否短路'),
    ('Boot from watchdog reset, software locked up check for firmware corruption',
     '看门狗复位启动：软件曾卡死，请检查固件是否损坏'),
    ('Encoder SPI fault, check encoder connections', '编码器 SPI 故障：请检查编码器接线'),
    ('Encoder SINCOS below min amplitude, check encoder connections and magnet alignment / distance',
     '正余弦编码器幅值过低：请检查编码器接线以及磁铁的对中和间距'),
    ('Encoder SINCOS above max amplitude, check encoder connections and magnet alignment / distance',
     '正余弦编码器幅值过高：请检查编码器接线以及磁铁的对中和间距'),
    ('Flash corruption, App config corrupt, rewrite app config to restore',
     'Flash 损坏：App 配置已损坏，请重新写入 App 配置以恢复'),
    ('Flash corruption, Motor config corrupt, rewrite motor config to restore',
     'Flash 损坏：电机配置已损坏，请重新写入电机配置以恢复'),
    ('Flash corruption, reflash firmware immediately!', 'Flash 损坏：请立即重新烧写固件！'),
    ('High offset on current sensor 1, check for hardware failure', '电流传感器 1 零点偏置过大：请检查硬件故障'),
    ('High offset on current sensor 2, check for hardware failure', '电流传感器 2 零点偏置过大：请检查硬件故障'),
    ('High offset on current sensor 3, check for hardware failure', '电流传感器 3 零点偏置过大：请检查硬件故障'),
    ('Unbalanced currents, check for hardware failure', '三相电流不平衡：请检查硬件故障'),
    ('BRK, hardware protection triggered, check for shorts or possible hardware failure',
     'BRK 硬件保护触发：请检查有无短路或硬件故障'),
    ('Encoder/Resolver: Loss of tracking', '编码器/旋变：失去跟踪'),
    ('Encoder/Resolver: Degradation of signal', '编码器/旋变：信号劣化'),
    ('Encoder/Resolver: Loss of signal', '编码器/旋变：信号丢失'),
    ('Encoder no magnet, magnet is too weak or too far from the encoder',
     '编码器检测不到磁铁：磁铁太弱或离编码器太远'),
    ('Magnet too strong, magnet is too strong or too close to the encoder',
     '磁铁太强：磁铁磁性太强或离编码器太近'),
    ('Phase filter fault, invalid phase filter readings', '相位滤波器故障：相位滤波器读数无效'),
    ('Encoder fault, check encoder connections and alignment', '编码器故障：请检查编码器接线和对中'),
]


def cstr(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


body = ['QString Utility::detectResultZh(QString res)',
        '{',
        '    // 汉化版：Utility::detectAllFoc() 的返回文本既用于判断成败（startsWith("Success!")），',
        '    // 又直接显示给用户。判断必须用英文原文，所以调用方拿原文做判断、拿这里的返回值做显示。',
        '    static const QList<QPair<QString, QString>> tab = {']
for en, zh in TABLE:
    body.append('        {%s, %s},' % (cstr(en), cstr(zh)))
body[-1] = body[-1].rstrip(',')
body += ['    };',
         '',
         '    for (const auto &p: tab) {',
         '        res.replace(p.first, p.second);',
         '    }',
         '',
         '    return res;',
         '}',
         '',
         '']
FUNC = '\n'.join(body)


def patch_impl():
    p = os.path.join(root, 'utility.cpp')
    src = open(p, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in src else '\n'
    func = FUNC.replace('\n', nl)
    anchor = 'QString Utility::detectAllFoc(VescInterface *vesc,'
    start = src.find('QString Utility::detectResultZh(QString res)')
    if start >= 0:
        end = src.index(anchor, start)
        if src[start:end] == func:
            print('已存在，跳过: utility.cpp')
            return
        src = src[:start] + func + src[end:]
        print('已更新: utility.cpp')
    else:
        assert src.count(anchor) == 1
        src = src.replace(anchor, func + anchor)
        print('已修改: utility.cpp')
    open(p, 'w', encoding='utf-8', newline='').write(src)


patch_impl()

# ---------------- 显示点 ----------------
patch('widgets/detectallfocdialog.cpp',
      'HelpDialog::showHelpMonospace(this, "FOC Detection Result", res);',
      'HelpDialog::showHelpMonospace(this, "FOC 检测结果", Utility::detectResultZh(res));')

patch('mobile/SetupWizardFoc.qml',
      '                resultDialog.title = "Detection Result"\n                resultLabel.text = res',
      '                resultDialog.title = "检测结果"\n                resultLabel.text = Utility.detectResultZh(res)')
