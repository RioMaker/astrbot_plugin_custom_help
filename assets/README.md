# 图像资源说明

## 插件 Logo

根目录的 [logo.png](../logo.png) 是自定义帮助插件的标识，采用叠层帮助卡片、对话气泡和问号，表达模板汇总与群聊帮助。配色沿用插件科技风的深蓝、青色和蓝紫色。

图片于 2026-11-17 使用内置 imagegen 工具生成，原始 PNG 为 1254 × 1254 像素、1:1 不透明背景，未做二次图像处理。完整生成提示词保存在 [logo-prompt.txt](logo-prompt.txt)。README 使用同一图片；插件内各帮助栏目的渲染样式仍由原有逻辑决定。

## 可可子帮助图资源

`keko-feeding.png` 原样复用本工作区 `astrbot_plugin_feed/assets/keko-feeding.png` 的可可子透明插画。原资源根据用户提供的五张人物参考图，于 2026-11-01 使用 imagegen 生成；浅绿双马尾、彩虹皇冠和发夹、红橙眼睛、蓝色耳机与水手服保持原样。

插画随本插件打包，仅用于生图帮助栏目及其续页装饰；运行时仅用 Pillow 等比缩放、透明合成，不依赖投喂插件，不调用图片生成服务。奶油底与浅绿卡片配色沿用投喂卡主题，标题和说明由当前帮助模板绘制。

字体沿用 `fonts/NotoSansSC-Regular.otf`，许可见 `fonts/OFL.txt`。

## 巧克力表情

`emoji/chocolate.png` 是 Google Noto Emoji 的 128 × 128 彩色巧克力图标，原图未修改，运行时按字号透明缩放。它补充中文字体中缺失的 `🍫`，同时用于帮助图的宽度计算和绘制，不依赖系统表情字体或在线服务。

- [原始 PNG](https://github.com/googlefonts/noto-emoji/blob/99701e07d3d1fe1bdbcdb14964547f0fd592966f/2D/png/128/emoji_u1f36b.png)
- 固定来源提交：`99701e07d3d1fe1bdbcdb14964547f0fd592966f`
- SHA-256：`b0bdcd8ad3585152a45a8ec9c2187e677c417c7132450f3b0a383fd470fcebd9`
- Apache License 2.0；完整许可见 [emoji/LICENSE](emoji/LICENSE)，原作者版权声明见 [emoji/NOTICE](emoji/NOTICE)。上游图像资源许可说明见 [README](https://github.com/googlefonts/noto-emoji/blob/99701e07d3d1fe1bdbcdb14964547f0fd592966f/README.md#license) 与 [SVG 资源声明](https://github.com/googlefonts/noto-emoji/blob/99701e07d3d1fe1bdbcdb14964547f0fd592966f/2D/svg/LICENSE)。
