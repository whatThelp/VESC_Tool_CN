# VESC Tool 汉化版 —— 交付说明

生成日期：2026-09-07（第一、二阶段全部完成，已实机验证）
生成机器：Windows 11 Pro x64（本机原生编译，非交叉编译）

---

## 1. 源码与版本

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/vedderb/vesc_tool |
| 分支 | master |
| commit | `dc53c658cbb89a947246034f7a00149cf79abdfc` |
| `VT_VERSION` | **7.01** |
| `VT_IS_TEST_VERSION` | 1（上游 master 目前就是开发版） |
| `VT_CONFIG_VERSION` | 4 |
| `VT_GIT_COMMIT` | 空（源码是 tar 包，无 .git） |

## 2. 编译环境

| 项 | 值 |
|---|---|
| Qt | **5.15.2**（win64_mingw81 预编译包，`D:\Qt5\5.15.2\mingw81_64`） |
| 编译器 | **MinGW-W64 GCC 8.1.0**（`D:\Qt5\Tools\mingw810_64`，与该 Qt 包配套） |
| qmake | `qmake -config release "CONFIG += release_win build_original exclude_fw"` |
| make | `mingw32-make -j8` |
| 结果 | **0 error / 0 warning** |
| 打包 | `windeployqt`（**不能加 `--release`**，见第 9 节） |

本机原有的 Qt 6.11.1 编不了 VESC Tool（`QT += gamepad` 在 Qt6 已移除，另有 QRegExp /
QDesktopWidget / QtGraphicalEffects / QtQuick.Extras / QtQuick.Controls.Styles /
QtQuick.Dialogs 等一批 Qt6 已删或改签名的用法）。Qt 5.15.2 装在独立目录，未动原有 Qt6，
未改系统 PATH。

## 3. 汉化范围与覆盖率

### 第一阶段：配置数据（参数标签 / 下拉选项 / 帮助文本）

`res/config/{6.06,7.00,7.01}/` 的 `parameters_mcconf.xml`、`parameters_appconf.xml`、`info.xml`。

| 版本 / 文件 | longName | enumNames | description |
|---|---|---|---|
| 6.06 / mcconf | 209/209 (100%) | 92/135 (68%) | 209/209 (100%) |
| 6.06 / appconf | 114/119 (95%) | 94/158 (59%) | 119/119 (100%) |
| 6.06 / info | 21/23 (91%) | — | 20/23 (86%) |
| 7.00 / mcconf | 211/211 (100%) | 102/146 (69%) | 211/211 (100%) |
| 7.00 / appconf | 117/122 (95%) | 95/159 (59%) | 121/122 (99%) |
| 7.00 / info | 23/25 (92%) | — | 22/25 (88%) |
| 7.01 / mcconf | 211/211 (100%) | 104/148 (70%) | 211/211 (100%) |
| 7.01 / appconf | 119/124 (95%) | 101/165 (61%) | 123/124 (99%) |
| 7.01 / info | 23/25 (92%) | — | 22/25 (88%) |

**为什么翻了三个版本**：`Utility::configLoadLatest()` 按 `VT_VERSION` 挑目录，
**未连接时程序读的是 `res/config/7.01/`**，只有连上 7.00 固件才读 7.00；而本项目的板子跑
6.06。其余 22 个版本目录（3.55～6.05）未改动。

### 第二阶段：界面骨架（菜单 / 导航 / 按钮 / 悬停提示 / 对话框 / 向导）

| 位置 | 覆盖率 |
|---|---|
| `*.ui` 的 text/toolTip/title/windowTitle/placeholderText（68 个文件） | **1125/1202 = 93%** |
| `*.ui` 的选项卡标题 | **104/117 = 88%** |
| `*.qml` 的 text/title/placeholderText/ToolTip.text（90 个文件） | **431/441 = 97%** |
| `*.cpp` 的 `tr()`（不含第三方 QCodeEditor） | **705/720 = 97%** |

另外还覆盖了 `.cpp` 里 `emitMessageDialog` / `QMessageBox` / `setText` / `addItem` /
`new QCheckBox(...)` 等调用和控件构造函数里的可见文本。

**右侧工具栏的悬停提示**（读取/写入电机配置、断开、重启、关机、CAN 转发、拉取实时数据、
IMU 采样、手柄控制等）在 `mainwindow.ui` 的 `toolTip` 里，已全部汉化 —— 见
`screenshots/06_toolbar_tooltip_cn.png`。

### 额外：Qt 内建文案

原版没装 `QTranslator`，Qt 自己的标准控件文案一直是英文。汉化版加载了两个翻译文件：

- `translations/qt_zh_CN.qm` —— Qt 自带的简体中文（文件对话框、输入框右键菜单等）
- `translations/vesc_cn_extra.qm` —— **本项目自己编的补充翻译**。Qt 5.15 的 `qt_zh_CN.qm`
  里没有 `QPlatformTheme` 上下文（标准按钮文案在 `qtbase_zh_CN.qm` 里，而这套 Qt 只提供
  了 zh_TW 版），所以确定/取消/是/否这些按钮原本仍是英文。源文件是
  `tools/vesc_cn_extra.ts`，用 `lrelease` 编译。

### 刻意保留英文的部分

1. **许可证与免责条款**：`gpl_text`（GPL 全文 60 KB）、`ios_license_text`、首启向导的
   LIMITED WARRANTY STATEMENT 正文。译文没有法律效力。同页的"使用须知"（安全操作指引，
   不是条款）**已翻译**。
2. **固件宏名 / 枚举常量**：`FOC_OBSERVER_MXLEMMING`、`CAN_BAUD_500K`、`IMU_TYPE_*`、
   `AHRS_MODE_*`、`BATTERY_TYPE_*`、`DOUBLE_32_AUTO`、`UINT_16` 等。
3. **型号 / 单位 / 格式名**：`AS5047 Encoder`、`KTY84/130`、`PT1000`、`RGB565`、`250 Hz`、
   `-18 dBm`、`CSV`/`PDF`/`PNG`、`STM32F40x`、`NRF52840 1M/256K`。
4. **代码与命令**：`QCodeEditor/QVescCompleter.cpp` 里的 QML/LispBM API 补全条目
   （`setDutyCycle(duty)`、`Math.sqrt(x)`）、终端命令 `help`、主机名 `veschub.vedder.se`、
   曲线图例缩写（`TM`/`TF`/`IM`/`II`/`VBus`）。
5. **品牌名**：`VESC Tool`、`VESC Discord`、`Victron Energy`。

### 译名约定

- `<longName>`（参数标签）用 `中文（English）`，例如 `电机相电流上限（Motor Current Max）`，
  保留英文原文才能对上网上的教程和论坛帖。
- 菜单、导航、按钮、悬停提示用纯中文（短、不撑布局）。
- `<description>` 正文全中文，首次出现的专业术语后括号附英文。
- FOC / BLDC / PWM / ERPM / HFI / MTPA / ADC / PPM / CAN / UART / SWD / BMS / IMU 等缩写保留英文。

## 4. ★ 对源码做的四处功能性改动

除字符串替换外只动了这四处（`patches/source_patches.diff` 是前三处的完整补丁）：

| 文件 | 改动 |
|---|---|
| `main.cpp` | 加载 `qt_zh_CN.qm` 和 `vesc_cn_extra.qm` 两个翻译文件 |
| `configparam.h` | 新增 `QStringList enumNamesSig` 字段 |
| `configparams.cpp` | 解析 `<enumNamesSig>`；`getSignature()` 改用它计算 |
| `mainwindow.cpp` | 三个页面名 `Terminal`/`QML Scripting`/`LispBM Scripting` 成对替换 |

最后一条要成对改的原因：这三项是 `addPageItem("Terminal", …)` 的裸字符串，而
`showPage("Terminal")` 用**同一个字符串当页面键**，只翻一边会直接把页面跳转打断。
（其余导航项都是 `tr(...)` 且没有任何 `showPage()` 引用，已核对过。）

### 为什么第 2、3 条是必须的（否则汉化版读不了真实固件的配置）

`ConfigParams::getSignature()` 把 **`enumNames` 的文本**算进配置签名：

```cpp
sigStr.append(name); sigStr.append(type); sigStr.append(vTx);
for (auto n: p->enumNames) sigStr.append(n);      // ← 下拉选项文本
return Utility::crc32c(...);
```

而固件端的签名常量是由**英文 XML** 生成的。一旦把下拉选项翻成中文，签名就变了，
`deSerialize()` 判定 `Invalid signature`，**读写电机/App 配置直接失败**。

修法：在 XML 里额外保存一份英文原名 `<enumNamesSig>`，签名只用它算，界面照常显示中文。
没有该元素时（原版 XML）自动回退到 `enumNames`，行为与原版完全一致。

三个版本、六个配置文件的签名实测：

| 版本/文件 | 原版(英文) | 汉化+未打补丁 | 汉化+打了补丁 |
|---|---|---|---|
| 6.06/mcconf | 0x2EFD0142 | 0xB5ACE0F0 ✗ | **0x2EFD0142 ✓** |
| 6.06/appconf | 0x7D217EB8 | 0x1F6772EA ✗ | **0x7D217EB8 ✓** |
| 7.00/mcconf | 0x57AD8F53 | 0xB96DF024 ✗ | **0x57AD8F53 ✓** |
| 7.00/appconf | 0x8E195E93 | 0xBFC07F4F ✗ | **0x8E195E93 ✓** |
| 7.01/mcconf | 0xBC09F8B0 | 0xA8E12AEB ✗ | **0xBC09F8B0 ✓** |
| 7.01/appconf | 0x11ADA6CC | 0x452908B1 ✗ | **0x11ADA6CC ✓** |

## 5. 交付物

```
vesc_tool_cn/
├─ MANIFEST.md                        本文件
├─ vesc_tool_cn_win64/                可直接运行的程序目录（约 129 MB）
│  ├─ vesc_tool_cn.exe                主程序
│  ├─ Qt5*.dll / platforms/ / QtQuick*/ …   Qt 运行时与 QML 模块
│  ├─ translations/qt_zh_CN.qm        Qt 自带简体中文
│  ├─ translations/vesc_cn_extra.qm   补充翻译（标准按钮）
│  └─ libgcc_s_seh-1.dll / libstdc++-6.dll / libwinpthread-1.dll
├─ config_cn_builtin/{6.06,7.00,7.01}/   本 exe 内置的配置（中文下拉 + enumNamesSig）
├─ config_cn_official/{6.06,7.00,7.01}/  给官方原版 exe 用的配置（英文下拉）
├─ res_config_cn_for_official.rcc        上面那份打成的外挂资源包（见第 6 节方式 B）
├─ patches/source_patches.diff           功能性源码改动
├─ tools/                                汉化流水线 + 3179 条译文词典 + 设备模拟器 + .ts 源文件
├─ screenshots/                          实机截图 6 张
└─ build_log_tail.txt
```

### 校验和

| 文件 | 字节 | md5 |
|---|---|---|
| `vesc_tool_cn_win64/vesc_tool_cn.exe` | 20911104 | `614ec0f4c22d51108649e0f70bf5a283` |
| `vesc_tool_cn_win64/translations/vesc_cn_extra.qm` | 2014 | `af0b2146b8f8282d255ced1f6eeac6f9` |
| `res_config_cn_for_official.rcc` | 2035122 | `25f1873c7e69d28df2b54d1cf24de6cd` |

`vesc_tool_cn.exe` 是 `PE32+ executable for MS Windows 5.02 (GUI), x86-64`。

## 6. 两种使用方式

### 方式 A：直接用编译好的程序（推荐，中文最完整）

把 `vesc_tool_cn_win64\` 整个目录拷到任意位置，双击 `vesc_tool_cn.exe`。不需要装 Qt。
菜单、导航、按钮、悬停提示、参数、帮助、Qt 标准对话框全中文，且配置签名与固件一致。

### 方式 B：不重编译，给现有官方 VESC Tool 换中文配置

`Utility::configPath()` 启动时会加载 `%APPDATA%\VESC\VESC Tool\res_config.rcc`，把其中的
`/res/config_download/` 注册进资源系统，并在两边都有同一文件时取**修改时间较新**的那个。

```
copy res_config_cn_for_official.rcc "%APPDATA%\VESC\VESC Tool\res_config.rcc"
```

然后启动官方原版 `vesc_tool_7.00.exe` / `7.01`，**参数标签和帮助文本变中文**。删掉即还原。

> ⚠ 这一份里的**下拉选项保持英文**。官方 exe 没有 `enumNamesSig` 补丁，翻了下拉选项会让
> 配置签名对不上，读写配置直接失败（见第 4 节）。想要中文下拉请用方式 A。
>
> 包内含全部 25 个版本目录（6.06/7.00/7.01 中文，其余 22 个英文原版）+ `fw.xml`，
> 不会丢掉对其它固件版本的支持。官方"下载配置"功能会覆盖同一路径，覆盖后重拷一次即可。

## 7. 自检与实机验证

### 静态校验

- **配置 XML 结构校验**（`tools/verify.py`）：三个版本 × 三个文件 × 两种变体**全部 OK**。
  五项检查：① 参数结构指纹（参数 ID、`cDefine`、`type`、`vTx`、min/max、小数位、`suffix`
  等所有不可翻译字段逐字相同）② `description` 的 HTML 标签序列（在原始文件文本上比对，
  不做 XML 反转义，避免把 `&amp;lt;` 误判成标签）③ `enumNames` 数量与顺序 ④ 配置签名基准
  ⑤ UTF-8 合法且可被 `ET.parse` 解析。
- 68 个 `.ui` 全部通过 XML 解析（0 失败）
- 90 个 `.qml` 全部通过 `qmllint`（0 失败；原版同样 0 失败）
- 完整重编译 **0 error / 0 warning**
- 扫描被翻译的 `.cpp`/`.qml` 行，确认**没有任何字符串被程序自己拿去比较或解析**
  （`%1` 之类的占位符全部完好保留）

### 实机验证（配自制设备模拟器）

在本机启动 `vesc_tool_cn.exe`，用 `tools/vesc_sim.py` 模拟一台跑 6.06 固件、硬件名
`DIY_70_80` 的电调，通过 TCP 连接。结果：

| 验证项 | 结果 |
|---|---|
| 程序启动、主窗口 | 正常，菜单/导航/按钮/状态栏全中文 |
| 首启介绍向导 | "欢迎使用 VESC® Tool"、"使用须知" 两页中文，排版正常 |
| 连接 | 状态栏 `已连接（TCP）到 127.0.0.1:65102，受限模式`，CAN 设备列表出现 `DIY_70_80 [本机]` |
| **读取电机配置** | 模拟器按**英文签名**发出配置，VESC Tool **正常接收并解出** |
| **配置数值** | 模拟器注入的特征值原样显示：电机相电流上限 = **123.45 A**、电池电流上限 = **67.89 A** |
| 中文下拉值 | `DRV8301 过流模式` 显示为 `限流` |
| 右侧工具栏悬停提示 | 悬停 ↑M 图标弹出 **"读取电机配置"** |
| Qt 标准按钮 | 消息框按钮显示 **"确定"** |

**第 4 节那套签名修复由此得到端到端确认**：模拟器用的是原版英文 XML 算出的签名
（`mcconf 0x2EFD0142` / `appconf 0x7D217EB8`），汉化版能正常读入而不是报 Invalid signature，
说明它与真实固件的签名是一致的。

截图：`screenshots/` 下 6 张（介绍页、使用须知、主界面、连接页、参数页含特征值、工具栏提示）。

## 8. 设备模拟器

`tools/vesc_sim.py`，用 VESC 包协议在 TCP 上假装成一台电调：

```bash
python tools/vesc_sim.py <原版vesc_tool>/res/config/6.06 65102 6 6
```

然后在 VESC Tool 的「连接 → TCP」里连 `127.0.0.1:65102`（默认值就是它）。

实现了：包分帧 + CRC16、`COMM_FW_VERSION`、`COMM_GET_VALUES`（随时间变化的温度/电流/
转速/电压）、`COMM_GET_MCCONF`/`COMM_GET_APPCONF`（按 `SerOrder` 和各参数 `vTx` 类型
序列化的完整配置，含 `vbAppendDouble32Auto` 的浮点编码）、`COMM_TERMINAL_CMD`。
`Conf.OVERRIDE` 可以注入特征值用于验证。

## 9. 已知问题与注意事项

1. **`windeployqt` 不能加 `--release`** —— 它会把 MinGW 的 release 插件误判成 debug 而全部
   过滤掉，报 `Unable to find the platform plugin.`。去掉该开关即可。
2. **`VT_GIT_COMMIT` 为空** —— "关于"里该字段是空的。要补的话在源码目录 `git init` 并提交
   一次，或把 `.pro` 里那行改成写死的哈希。
3. **`VT_IS_TEST_VERSION = 1`** —— 上游 master 当前就是开发版，版本号带测试版标记，启动时
   会弹一次"VESC Tool 测试版"提示。
4. **参数编辑器保存 XML 会丢 `enumNamesSig`** —— `getXML()` 不写出该元素。日常调参不受影响；
   真要走这条路，重新跑一次 `tools/add_sig.py` 补回来即可。
5. **模拟器不实现的命令** —— `COMM_GET_VALUES_SELECTIVE`、IMU、BMS 等未实现，相关页面在
   连模拟器时不会有数据。这是模拟器的边界，不是汉化的问题。
6. **布局未逐页目视核对** —— 主界面、连接页、参数页、向导页都看过，中文比英文短，没有发现
   撑坏或截断。但没有把所有页面逐一截图比对。发现问题时改对应 XML 的 `<longName>` 即可，
   用方式 B 免重编译生效。
7. **注册表副作用** —— 验证运行时程序在 `HKCU\Software\VESC\VESC Tool` 下写了默认设置，
   并把 `intro_done` 置为 `false`。后果是下次启动任何版本的 VESC Tool 会再弹一次首启介绍
   向导，点完即可，不影响电调配置。

## 10. 汉化流水线（可复用）

`tools/` 下是整套脚本，换新版本 VESC Tool 时直接重跑，不用重新翻译（词典按**英文原文的
md5** 索引，没变过的条目自动命中）：

| 文件 | 作用 |
|---|---|
| `extract.py` / `apply.py` | 第一阶段：配置 XML。只碰 `<longName>/<enumNames>/<description>`；description 内只碰转义 HTML 的文本节点，标签/style/转义一律不动。跳过 `gpl_text`/`ios_license_text`。 |
| `extract2.py` / `apply2.py` | 第二阶段：`.ui`（属性白名单，跳过 `notr="true"` 和自闭合 `<string/>`）、`.qml`（属性白名单 + 跨行 `+` 拼接续行）、`.cpp`（`tr()` + 目标调用 + 控件构造函数 + C++ 相邻字面量拼接）。 |
| `add_sig.py` | 给译后 XML 补 `<enumNamesSig>`（配置签名用的英文原名）。 |
| `verify.py` | 第 7 节的五项结构校验，自动识别两种交付变体。 |
| `mkbatch.py` / `mkbatch2.py` | 按首次出现顺序切批次。 |
| `vesc_sim.py` | 第 8 节的设备模拟器。 |
| `vesc_cn_extra.ts` | Qt 标准按钮的补充翻译源文件（`lrelease` 编译成 .qm）。 |
| `trans/*.json` | 译文词典，**3179 条**，键是英文原文的 md5 前 10 位。 |

回填一律是"只替换片段所占的那一段字节，其余逐字节保留"，并自动保留原文的前后空白
（很多 QML/C++ 字符串靠尾部空格与下一段拼接），因此 diff 干净、缩进不变。

### 踩过的坑（换版本重跑时留意）

- `.ui` 里 `<string notr="true"/>` 是自闭合标签且本就标记为"不翻译"，正则只匹配无属性的
  `<string>` 才安全，否则会吞掉一大段 XML。
- C++/QML 里 `"前半句 " "后半句"` 和 `"a" + "b"` 的拼接必须一并抓，否则界面上会剩半句英文。
- "内容不得含 `<`" 这条保险只能用于 `.ui`；C++/QML 里 `<br>`、`<b>` 是合法文本。
- `tr()` 是 Qt 里"这段给用户看"的标记，是最可靠的抓取入口。
