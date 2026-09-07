# VESC Tool 汉化版（简体中文）

基于 [vesc_tool](https://github.com/vedderb/vesc_tool) 上游 `master`
（commit `dc53c658cbb89a947246034f7a00149cf79abdfc`，`VT_VERSION = 7.01`）编译的简体中文版
VESC Tool，Windows x64。

VESC Tool 本身没有接入 Qt 的翻译框架（`.pro` 里没有 `TRANSLATIONS`，整个仓库没有
`.ts`/`.qm`），所以丢语言包是不起作用的 —— 汉化的做法是**直接改源文件里的文本再重新编译**。

## 汉化了什么

| 位置 | 覆盖率 |
|---|---|
| 配置 XML 的参数标签 `longName` | 100%（6.06 / 7.00 / 7.01 三个版本） |
| 配置 XML 的帮助文本 `description` | ~99% |
| `.ui` 的按钮/标题/**悬停提示** | 93% |
| `.qml` 的界面文本 | 97% |
| `.cpp` 的 `tr()`（对话框、状态栏、向导） | 97% |
| Qt 标准控件（确定/取消/文件对话框…） | 已补齐 |

刻意保留英文：许可证与免责条款正文、固件宏名与枚举常量（`FOC_OBSERVER_*`、`CAN_BAUD_*`）、
MCU 与传感器型号、单位与格式名、LispBM/QML 的 API 补全条目。

参数标签用 `中文（English）` 的形式（例如 `电机相电流上限（Motor Current Max）`），
保留英文原文是为了还能对上网上的教程和论坛帖。

## 目录

```
vesc_tool_cn_win64/                可直接运行的程序目录（解压即用，不需要装 Qt）
config_cn_builtin/{6.06,7.00,7.01} 本 exe 内置的配置（中文下拉 + enumNamesSig）
config_cn_official/{...}           给官方原版 exe 用的配置（英文下拉）
res_config_cn_for_official.rcc     上面那份打成的外挂资源包，免重编译
patches/source_patches.diff        对上游源码的功能性改动（见下）
tools/                             汉化流水线脚本 + 译文词典 + VESC 设备模拟器
screenshots/                       实机截图
MANIFEST.md                        完整交付说明（校验和、验证过程、已知问题）
```

## 两种用法

**A. 直接用编译好的程序**：把 `vesc_tool_cn_win64\` 拷到任意位置，双击 `vesc_tool_cn.exe`。

**B. 不重编译，给官方原版换中文配置**：

```
copy res_config_cn_for_official.rcc "%APPDATA%\VESC\VESC Tool\res_config.rcc"
```

然后启动官方 `vesc_tool_7.00.exe` / `7.01`，参数标签和帮助文本变中文。删掉即还原。
这一份的**下拉选项保持英文**，原因见下。

## ★ 一个必须注意的点：配置签名

`ConfigParams::getSignature()` 把 `enumNames`（下拉选项）的**文本**算进配置签名，而固件端的
签名常量是按英文 XML 生成的。**把下拉选项翻成中文，签名就会对不上，读写电机/App 配置会被判
`Invalid signature` 直接失败。**

本项目的修法：在 XML 里额外保存一份英文原名 `<enumNamesSig>`，让签名只用它计算，界面照常
显示中文；没有该元素时自动回退到 `enumNames`，对原版 XML 行为不变。

因此给**官方原版 exe** 用的外挂配置包必须保持英文下拉（官方 exe 没有这个补丁）。
想要中文下拉，请用方式 A。

## 对上游源码的改动

除字符串替换外只有四处，完整补丁见 `patches/source_patches.diff`：

1. `main.cpp` —— 加载 `qt_zh_CN.qm` 和自制的 `vesc_cn_extra.qm`（Qt 5.15 的 `qt_zh_CN.qm`
   缺 `QPlatformTheme` 上下文，标准按钮文案本来是英文）
2. `configparam.h` —— 新增 `enumNamesSig` 字段
3. `configparams.cpp` —— 解析 `<enumNamesSig>`，签名改用它计算
4. `mainwindow.cpp` —— `Terminal` / `QML Scripting` / `LispBM Scripting` 三个页面名成对替换
   （`addPageItem()` 和 `showPage()` 共用同一字符串当页面键，只翻一边会打断页面跳转）

## 编译环境

Qt 5.15.2（win64_mingw81）+ MinGW-W64 GCC 8.1.0，
`qmake -config release "CONFIG += release_win build_original exclude_fw"`，0 error / 0 warning。
详见 `MANIFEST.md` 第 2 节。

> 注意：`windeployqt` **不能加 `--release`**，它会把 MinGW 的 release 插件误判成 debug
> 而全部过滤掉，报 `Unable to find the platform plugin.`。

## 验证

没有实机电调，所以写了 `tools/vesc_sim.py` —— 用 VESC 的包协议在 TCP 上模拟一台跑 6.06 固件的
电调，实现了分帧 + CRC16、固件版本、实时数据、以及按 `SerOrder` 和各参数 `vTx` 类型完整序列化
的配置。它的签名一律用**原版英文 XML** 计算（和真实固件一致）。

汉化版能正常连接并读入配置，模拟器注入的特征值（电机相电流上限 123.45 A、电池电流上限
67.89 A）在界面上原样显示 —— 这端到端确认了签名修复是对的。详见 `MANIFEST.md` 第 7 节。

## 许可与商标

- VESC Tool 采用 **GNU GPL v3**，本仓库同样遵循，`LICENSE` 为上游许可证原文。
- 完整源码请见上游仓库 https://github.com/vedderb/vesc_tool
  （commit `dc53c658cbb89a947246034f7a00149cf79abdfc`），本仓库的改动全部在
  `patches/source_patches.diff` 和 `config_cn_builtin/` 里。
- **VESC® 是 Benjamin Vedder 的注册商标。** 上游明确不鼓励在官方渠道之外发布 VESC Tool 的
  二进制版本，参见 [trademark policies](https://vesc-project.com/trademark_policies)。
  本仓库仅作个人调参自用，不是官方发布，也不代表 VESC Project。
  官方版本请从 https://vesc-project.com/ 下载。
