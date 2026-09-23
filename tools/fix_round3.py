# -*- coding: utf-8 -*-
"""第三轮修正：全功能复测时发现的遗留英文（都只影响显示）。

逐条"原文 -> 译文"定点替换，可重复执行：原文还在就替换（并核对次数），
原文不在而译文在就跳过，两者都不在则报错（说明上游源码变了，需要人工看）。

动之前逐一确认过这些字符串只用于显示，没有被拿去做比较/当键用：
  * QML 向导的用途名、电机名、标签页名、按钮文字 —— 只有 text: / model: 在用
  * commands.cpp 的 ackReceived 文本 —— 只流向 VescInterface::statusMessage（状态栏）
  * 配置 XML 里的 ::sep:: 分组标题 —— 不参与配置签名（getSignature 只用
    SerOrder 的参数名、type、vTx、enumNamesSig），代码里只判断 startsWith("::sep::")

用法: python fix_round3.py <源码根> [额外的 config 目录 ...]
"""
import os, sys

root = sys.argv[1]
extra_cfg = sys.argv[2:]
log = []


def rep(rel, pairs, base=None):
    p = os.path.join(base or root, rel)
    src = open(p, encoding='utf-8', newline='').read()
    new = src
    nl = '\r\n' if '\r\n' in src else '\n'
    done = skip = 0
    for item in pairs:
        old, zh = item[0].replace('\n', nl), item[1].replace('\n', nl)
        cnt = item[2] if len(item) > 2 else None
        c = new.count(old)
        if c:
            assert cnt is None or c == cnt, '%s: %r 期望 %s 处，实际 %d 处' % (rel, old, cnt, c)
            new = new.replace(old, zh)
            done += c
        elif zh in new:
            skip += 1
        else:
            raise SystemExit('%s: 原文和译文都找不到: %r' % (rel, old))
    if new != src:
        open(p, 'w', encoding='utf-8', newline='').write(new)
    log.append('%-45s 替换 %3d 处，已是译文 %2d 条' % (rel if base is None else p, done, skip))


# ---------------- QML FOC 向导 ----------------
rep('mobile/SetupWizardFoc.qml', [
    ('"↓ Only change if needed ↓"', '"↓ 以下参数仅在需要时修改 ↓"'),
    ('name: "Generic"', 'name: "通用"'),
    ('name: "E-Skate"', 'name: "电动滑板"'),
    ('name: "Balance"', 'name: "平衡车 / 独轮车"'),
    ('name: "Propeller"', 'name: "螺旋桨"'),
    ('qsTr("Override (Advanced)")', 'qsTr("手动覆盖（高级）")', 2),
    # 电机名与旧版 FOC 检测对话框（detectallfocdialog.cpp）的译名保持一致
    ('"Mini Outrunner (~75 g)"', '"微型外转子（约 75 g）"'),
    ('"Small Outrunner (~200 g)"', '"小型外转子（约 200 g）"'),
    ('"Medium Outrunner (~750 g)"', '"中型外转子（约 750 g）"'),
    ('"Large Outrunner (~2000 g)"', '"大型外转子（约 2000 g）"'),
    ('"Small Inrunner (~200 g)"', '"小型内转子（约 200 g）"'),
    ('"Medium Inrunner (~750 g)"', '"中型内转子（约 750 g）"'),
    ('"Large Inrunner (~2000 g)"', '"大型内转子（约 2000 g）"'),
    ('"E-Bike DD hub motor (~6 kg)"', '"电动自行车直驱轮毂电机（约 6 kg）"'),
    ('"EDF Inrunner Small (~200 g)"', '"小型涵道内转子（约 200 g）"'),
    ('prefix: "Max Power Loss : "', 'prefix: "最大功率损耗："'),
    ('prefix: "Openloop ERPM  : "', 'prefix: "开环电气转速："'),
    ('prefix: "Sensorless ERPM: "', 'prefix: "无感电气转速："'),
    ('prefix: "Motor Poles    : "', 'prefix: "电机极数："'),
    ('qsTr("Advanced (0 = defaults)")', 'qsTr("高级（0 = 使用默认值）")'),
    ('prefix: "Battery Current Regen: "', 'prefix: "电池最大回充电流："'),
    ('prefix: "Battery Current Max: "', 'prefix: "电池最大放电电流："'),
    ('qsTr("Gear Ratio")', 'qsTr("传动比")'),
    ('qsTr("Motor Pulley")', 'qsTr("电机端齿数")'),
    ('qsTr("Wheel Pulley")', 'qsTr("轮端齿数")'),
    ('model: ["Usage", "Motor", "Battery", "Setup", "Direction"]',
     'model: ["用途", "电机", "电池", "设置", "方向"]'),
    ('"Not connected to the VESC. Please connect in order to run detection."',
     '"未连接 VESC。请先连接，再运行检测。"'),
    ('nextButton.text = "Finish"', 'nextButton.text = "完成"'),
    ('nextButton.text = "Run Detection"', 'nextButton.text = "运行检测"'),
    ('nextButton.text = "Next"', 'nextButton.text = "下一步"'),
    ('prevButton.text = "Cancel"', 'prevButton.text = "取消"'),
    ('prevButton.text = "Previous"', 'prevButton.text = "上一步"'),
])

rep('mobile/DirectionSetup.qml', [
    ('{"name": "This VESC"', '{"name": "本机 VESC"'),
    ('{"name": "VESC on CAN-bus"', '{"name": "CAN 总线上的 VESC"'),
    ('qsTr("Select which VESCs have inverted motor direction. Press the FWD or REV button to try.")',
     'qsTr("选择哪些 VESC 的电机方向是反的。可以按“正转”或“反转”按钮试一下。")'),
])

# ---------------- 欢迎页右侧面板 / 仪表盘 / 连接页 ----------------
rep('res/qml/WelcomeQmlPanel.qml', [
    ('"Not connected. Please connect in order to run the FOC wizard."',
     '"未连接。请先连接 VESC，再运行 FOC 向导。"'),
    ('"You are not connected to the VESC. Please connect in order " +\n'
     '                                     "to quick pair an NRF-based remote."',
     '"未连接 VESC。请先连接，再快速配对基于 NRF 的遥控器。"'),
    ('"You are not connected to the VESC. Please connect in order " +\n'
     '                                     "to map directions."',
     '"未连接 VESC。请先连接，再设置电机方向。"'),
    ('"You are not connected to the VESC."', '"未连接 VESC。"'),
    ('"The BLE module does not support setup. You can try " +\n'
     '                                         "updating the firmware on it from the SWD programmer page."',
     '"该蓝牙模块不支持配置。可以到 SWD 烧录器页面尝试更新它的固件。"'),
    ('model: ["RT Data", "Profiles"]', 'model: ["实时数据", "配置档"]'),
    ('buttonText: "Connect"', 'buttonText: "连接"'),
    ('"After clicking OK the VESC will be put in pairing mode for 10 seconds. Switch" +\n'
     '                "on your remote during this time to complete the pairing process."',
     '"点击确定后，VESC 会进入 10 秒配对模式。请在这段时间内打开遥控器以完成配对。"'),
    ('"The hardware you are connecting to contains code that will alter the " +\n'
     '                    "user interface of VESC Tool. This code has not been verified by the " +\n'
     '                    "authors of VESC Tool and could contain bugs and security problems. \\n\\n" +\n'
     '                    "Do you want to load this custom user interface?"',
     '"你连接的硬件包含会修改 VESC Tool 界面的代码。这些代码未经 VESC Tool 作者审核，" +\n'
     '                    "可能存在缺陷和安全问题。\\n\\n" +\n'
     '                    "要加载这个自定义界面吗？"'),
])

rep('mobile/RtDataSetup.qml', [
    ('typeText: "Current"', 'typeText: "电流"'),
    ('typeText: "Duty"', 'typeText: "占空比"'),
    ('typeText: "Power"', 'typeText: "功率"'),
    ('typeText: "Speed"', 'typeText: "速度"'),
    ('qsTr("Update Odometer")', 'qsTr("修改总里程")'),
    ('qsTr("Settings")', 'qsTr("设置")'),
    ('typeText: "TEMP\\nESC"', 'typeText: "电调\\n温度"'),
    ('typeText: "TEMP\\nMOTOR"', 'typeText: "电机\\n温度"'),
    ('typeText: "Consump."', 'typeText: "能耗"'),
    ('rangeLabel.text = useImperial ? "MI\\nRANGE" : "KM\\nRANGE"',
     'rangeLabel.text = useImperial ? "续航\\n英里" : "续航\\n公里"'),
])

rep('mobile/ConnectScreen.qml', [
    ('qsTr("Hide")', 'qsTr("隐藏")'),
    ('qsTr("Devices Found")', 'qsTr("发现的设备")'),
    ('qsTr("Scan...")', 'qsTr("扫描…")', 2),
    ('var text = "Scanning"', 'var text = "扫描中"'),
    ('"Connection timed out"', '"连接超时"'),
    ('"This is going to clear all previous TCP hub connections. Continue?"',
     '"这会清除之前所有的 TCP Hub 连接。继续吗？"'),
])

# ---------------- 旧版 FOC 检测对话框 / 方向设置 ----------------
rep('widgets/detectallfocdialog.ui', [
    ('<attribute name="label">\n           <string>Motor</string>',
     '<attribute name="label">\n           <string>电机</string>'),
    ('<attribute name="label">\n           <string>Battery</string>',
     '<attribute name="label">\n           <string>电池</string>'),
    ('<attribute name="label">\n           <string>Setup</string>',
     '<attribute name="label">\n           <string>设置</string>'),
    ('<attribute name="label">\n           <string>Directions</string>',
     '<attribute name="label">\n           <string>方向</string>'),
])
rep('widgets/dirsetup.cpp', [('addViewer(QString("Local VESC"), -1)', 'addViewer(QString("本机 VESC"), -1)')])
rep('widgets/dirsetup.ui', [('可以按 FWD 或 REV 按钮试一下。', '可以按“正转”或“反转”按钮试一下。')])

# ---------------- 状态栏 / 底部指示条 / 实时数据曲线 ----------------
rep('commands.cpp', [
    ('emit ackReceived("Motor config write OK");', 'emit ackReceived("电机配置写入成功");'),
    ('emit ackReceived("App config write OK");', 'emit ackReceived("App 配置写入成功");'),
    ('emit ackReceived("COMM_SET_MCCONF_TEMP Write OK");', 'emit ackReceived("临时电机配置写入成功");'),
    ('emit ackReceived("COMM_SET_MCCONF_TEMP_SETUP Write OK");', 'emit ackReceived("临时电机配置（Setup）写入成功");'),
    ('emit ackReceived("COMM_SET_BATTERY_CUT Write OK");', 'emit ackReceived("电池截止电压写入成功");'),
])
rep('mainwindow.cpp', [('ui->dispDuty->setName("Duty");', 'ui->dispDuty->setName("占空比");')])
rep('widgets/displaybar.cpp', [('mName = "Current";', 'mName = "电流";')])
rep('pages/pagertdata.cpp', [
    ('setName("Current in")', 'setName("输入电流")'),
    ('setName("Current motor")', 'setName("电机电流")'),
    ('setName("Duty cycle")', 'setName("占空比")'),
    ('setName("D Current")', 'setName("D 轴电流")'),
    ('setName("Q Current")', 'setName("Q 轴电流")'),
    ('setName("D Voltage")', 'setName("D 轴电压")'),
    ('setName("Q Voltage")', 'setName("Q 轴电压")'),
    ('setName("Temperature MOSFET")', 'setName("MOSFET 温度")'),
    ('setName("Temperature MOSFET 1")', 'setName("MOSFET 1 温度")'),
    ('setName("Temperature MOSFET 2")', 'setName("MOSFET 2 温度")'),
    ('setName("Temperature MOSFET 3")', 'setName("MOSFET 3 温度")'),
    ('setName("Temperature Motor")', 'setName("电机温度")'),
    ('yAxis->setLabel("Ampere (A)")', 'yAxis->setLabel("电流（A）")'),
    ('yAxis2->setLabel("Duty Cycle")', 'yAxis2->setLabel("占空比")'),
    ('yAxis->setLabel("Temperature MOSFET (\\u00B0C)")', 'yAxis->setLabel("MOSFET 温度（\\u00B0C）")'),
    ('yAxis2->setLabel("Temperature Motor (\\u00B0C)")', 'yAxis2->setLabel("电机温度（\\u00B0C）")'),
    ('focPlot->yAxis->setLabel("Current")', 'focPlot->yAxis->setLabel("电流")'),
    ('focPlot->yAxis2->setLabel("Voltage")', 'focPlot->yAxis2->setLabel("电压")'),
])

# 各页曲线的时间轴
tot = 0
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d not in ('build', '.git')]
    for f in fn:
        if f.endswith('.cpp'):
            p = os.path.join(dp, f)
            s = open(p, encoding='utf-8', newline='').read()
            c = s.count('setLabel("Seconds (s)")')
            if c:
                open(p, 'w', encoding='utf-8', newline='').write(s.replace('setLabel("Seconds (s)")', 'setLabel("时间（s）")'))
                tot += c
log.append('各页曲线时间轴 "Seconds (s)" 替换 %d 处' % tot)

# ---------------- 配置 XML 的分组标题 ----------------
SEP = {
    'ABI Encoder': 'ABI 编码器', 'Address': '地址', 'Battery': '电池',
    'CAN Messages Rate 1': 'CAN 报文速率 1', 'CAN Messages Rate 2': 'CAN 报文速率 2',
    'Coasting Brake': '滑行制动', 'Common': '通用', 'Current': '电流', 'Encoder': '编码器',
    'General': '常规', 'Integrity': '完整性校验', 'Motor': '电机',
    'Motor Temperature Sensor Type': '电机温度传感器类型',
    'Multiple ESCs over CAN-bus': 'CAN 总线多电调', 'Multiple VESCs over CAN': 'CAN 总线多 VESC',
    'Multiple VESCs over CAN-bus': 'CAN 总线多 VESC', 'Offsets': '零点偏置',
    'Position Controller': '位置控制器', 'Radio': '射频', 'Rotation': '旋转',
    'Sin/Cos Encoder': '正余弦编码器', 'Smart Reverse': '智能倒车',
    'Speed Controller': '速度控制器', 'Voltage': '电压', 'Voltage Undriven': '未驱动时的电压',
    # ADC 1 / ADC 2 / AHRS / DRV8301 / MOSFET 是型号或缩写，保留
}
cfg_dirs = [os.path.join(root, 'res', 'config', v) for v in ('6.06', '7.00', '7.01')] + extra_cfg
for d in cfg_dirs:
    for f in ('parameters_mcconf.xml', 'parameters_appconf.xml'):
        p = os.path.join(d, f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding='utf-8', newline='').read()
        n = 0
        for en, zh in SEP.items():
            tag = '<param>::sep::%s</param>' % en
            n += s.count(tag)
            s = s.replace(tag, '<param>::sep::%s</param>' % zh)
        open(p, 'w', encoding='utf-8', newline='').write(s)
        log.append('分组标题 %2d 处  %s' % (n, p))

print('\n'.join(log))
