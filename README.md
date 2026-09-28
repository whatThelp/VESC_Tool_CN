# VESC Tool 简体中文版 —— 编译好的程序（v1.2）

这个 `release` 分支只放**编译好的程序**，源码、使用教程、测试报告都在 [`master` 分支](https://github.com/whatThelp/VESC_Tool_CN/tree/master)。

## 下载

| 文件 | 说明 | 直接下载 |
|---|---|---|
| `VESC_Tool_CN_v1.2_win64.zip` | **程序本体**（55 MB）。解压后双击 `vesc_tool_cn_win64\vesc_tool_cn.exe`，不需要装 Qt | [下载](https://github.com/whatThelp/VESC_Tool_CN/raw/release/VESC_Tool_CN_v1.2_win64.zip) |
| `res_config_cn_for_official.rcc` | 可选。给**官方原版** VESC Tool 换中文参数说明，拷到 `%APPDATA%\VESC\VESC Tool\res_config.rcc` | [下载](https://github.com/whatThelp/VESC_Tool_CN/raw/release/res_config_cn_for_official.rcc) |
| `SHA256SUMS.txt` | 校验值 | [查看](SHA256SUMS.txt) |

也可以点上面的文件名进去，再点右上角的「Download raw file」。
国内下载慢的话，可以到 Gitee 的发行版下载同样的文件：<https://gitee.com/wowhywhat/vesc_-tool_-cn/releases>

```
18a958a625dc6bebb0c2f94e7d3c85a6caf45386c0552259a2a561d8b87919c7  VESC_Tool_CN_v1.2_win64.zip
23d346a62f9730fbf4ea933e665c8a3a041d1e2cc4ba4e84a10ad06f7d5e0d3e  res_config_cn_for_official.rcc
```

## 版本

- 汉化版 **v1.2**，VESC Tool **7.00**（上游 master `dc53c658`），Windows x64
- 对应源码：`master` 分支的 `v1.2` 标签；`patches/full_source.diff` 打到上游源码上即可得到编译本程序所用的源码
- 使用教程：[TUTORIAL.md](https://github.com/whatThelp/VESC_Tool_CN/blob/master/TUTORIAL.md)（从电机参数识别到用速度控制启动电机）
- 测试报告：[TEST_REPORT.md](https://github.com/whatThelp/VESC_Tool_CN/blob/master/TEST_REPORT.md)

## v1.2 相对 v1.1 的变化

- **[严重] 修复 FOC 电机配置向导打不开**：v1.1 的包缺 QML 运行库，欢迎页右侧空白、点向导没反应。v1.1 用户请整个替换。
- FOC 检测结果对话框改为中文；位域参数不再多出「未使用」勾选框。
- 补齐遗留英文，去掉中文句子里多余的空格。
- 附带 OpenSSL 1.1.1w，固件下载、扩展包商店等 HTTPS 功能可用（许可证见 `vesc_tool_cn_win64\licenses\`）。

## 说明

VESC® 是 Benjamin Vedder 的注册商标。本版本仅供个人调参自用，不是官方发布；官方版本请从 <https://vesc-project.com/> 下载。
VESC Tool 采用 GPL-3.0。
