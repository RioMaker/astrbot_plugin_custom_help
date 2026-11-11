# 插件帮助内容来源与范围

全库核对日期：2026-11-06；生图说明于 2026-11-10 更新至本地 v0.3.8。说明库来自当前工作区上一级目录中的插件元数据、README 和实际指令入口；不扫描或导入其他插件的 Python 模块。

## 范围与版本

- 共发现 20 个 `astrbot_plugin_*` 目录，对应 19 个唯一运行时插件标识。全部纳入 `help_catalog.json`，每个插件只生成一份默认说明。
- `astrbot_plugin_junjunget` 的实际元数据已是 `astrbot_plugin_welcome_qqgroup` / v1.4.0；它与正式欢迎插件目录同名、同用途，不重复显示。此处只合并帮助项，不合并仓库或迁移清单。
- `astrbot_plugin_usage_stats` 在本地存在，版本为 0.2.0，但未出现在此次 HTTP 部署附件或父目录迁移清单中；按本地插件纳入，默认不展示。
- 附件中你维护的 14 个已启用插件，其帮助默认开启；已停用的可可子人格管理、星轨神谕，以及附件中未出现的分析、Grok、使用统计默认关闭。该初始选择仅供帮助配置初始化，不能据此修改其他插件的真实启用状态。
- 紫微附件部署版本为 2.3.1，本地已为 2.3.3；种子中的主要指令均为 2.3.1 已有入口，2.3.2/2.3.3 为图片布局调整。自定义帮助 2.3.0 为当前本地版本，附件仍为 1.0.0。
- 说明库按本地源码能力整理。相同版本字符串不代表本地工作区与运行服务器的代码逐字相同；星轨神谕 README 明确其紫微星图仍处于本地预览阶段，保留在默认关闭的说明中。
- 五行数字卦保留运行标识 `wuxing_num` 和作者元数据；其安装来源属于 RioMaker，按用户维护范围收录，不据此改写原创署名。

## 数据字段

`help_catalog.json` 顶层为 `plugins` 数组。`id` 是元数据的运行标识，`directory` 是核对时的本地目录，`version` 是说明对应的本地版本，`title`、`summary`、`body` 是可编辑的纯文字默认内容。`default_enabled` 是初始化时的帮助展示选择。`aliases` 只用于匹配历史标识或目录，不是聊天命令别名。

标题、摘要和正文不含 HTML。每份正文保留常用用户入口及必要权限说明；完整的高风险管理指令、模型配置与详细参数请查对应插件文档。生日等示例使用插件文档的虚构演示资料。后台编辑后的用户内容应保留。可选的 `previous_bodies` 列出确认过的旧版默认正文；重载时仅精确匹配这些原文的栏目更新为当前 `body`，标题、开关、顺序和自行修改的正文保留。启用说明总字数会超过上限时保留旧正文。

## 逐插件清单

| 名称 | 运行标识 | 本地版本 | 附件状态 | 默认帮助 | 核对来源 |
| --- | --- | --- | --- | --- | --- |
| 太鼓 · 今日人品 | `astrbot_plugin_taiko_rp` | 0.7.3 | 启用 0.7.3 | 开启 | [元数据](../../astrbot_plugin_rp_taikover-master/metadata.yaml)、[说明](../../astrbot_plugin_rp_taikover-master/README.md)、[指令源码](../../astrbot_plugin_rp_taikover-master/main.py) |
| RTLink · 太鼓成绩 | `rt_link` | v0.22.0 | 启用 v0.22.0 | 开启 | [元数据](../../astrbot_plugin_rt_link/metadata.yaml)、[说明](../../astrbot_plugin_rt_link/README.md)、[指令源码](../../astrbot_plugin_rt_link/main.py) |
| 六爻起卦 | `astrbot_plugin_liuyao` | 0.33.3 | 启用 0.33.2 | 开启 | [元数据](../../astrbot_plugin_liuyao/metadata.yaml)、[说明](../../astrbot_plugin_liuyao/README.md)、[指令源码](../../astrbot_plugin_liuyao/main.py) |
| 五行数字卦 | `wuxing_num` | v1.7.0 | 启用 v1.7.0 | 开启 | [元数据](../../astrbot_plugin_wuxing_num/metadata.yaml)、[说明](../../astrbot_plugin_wuxing_num/README.md)、[指令源码](../../astrbot_plugin_wuxing_num/main.py) |
| 紫微斗数排盘 | `astrbot_plugin_ziwei` | 2.3.3 | 启用 2.3.1 | 开启 | [元数据](../../astrbot_plugin_ziwei/metadata.yaml)、[说明](../../astrbot_plugin_ziwei/README.md)、[指令源码](../../astrbot_plugin_ziwei/main.py) |
| 干支纪时 | `astrbot_plugin_ganzhi` | 0.3.0 | 启用 0.3.0 | 开启 | [元数据](../../astrbot_plugin_ganzhi/metadata.yaml)、[说明](../../astrbot_plugin_ganzhi/README.md)、[指令源码](../../astrbot_plugin_ganzhi/main.py) |
| AI 生图与动图 | `astrbot_plugin_img_gener` | 0.3.8 | 启用 0.3.3 | 开启 | [元数据](../../astrbot_plugin_img_gener/metadata.yaml)、[说明](../../astrbot_plugin_img_gener/README.md)、[指令源码](../../astrbot_plugin_img_gener/main.py) |
| 思考气泡 | `astrbot_plugin_think_bubble` | 1.2.0 | 启用 1.2.0 | 开启 | [元数据](../../astrbot_plugin_think_bubble/metadata.yaml)、[说明](../../astrbot_plugin_think_bubble/README.md)、[指令源码](../../astrbot_plugin_think_bubble/main.py) |
| 投喂与赞助 | `astrbot_plugin_feed` | 0.3.0 | 启用 0.3.0 | 开启 | [元数据](../../astrbot_plugin_feed/metadata.yaml)、[说明](../../astrbot_plugin_feed/README.md)、[指令源码](../../astrbot_plugin_feed/main.py) |
| QQ 群入群欢迎 | `astrbot_plugin_welcome_qqgroup` | v1.4.0 | 启用 v1.4.0 | 开启 | [元数据](../../astrbot_plugin_welcome_qqgroup/metadata.yaml)、[说明](../../astrbot_plugin_welcome_qqgroup/README.md)、[指令源码](../../astrbot_plugin_welcome_qqgroup/main.py) |
| 门禁与积分 | `astrbot_plugin_access_gate` | 2.4.2 | 启用 2.4.0 | 开启 | [元数据](../../astrbot_plugin_access_gate/metadata.yaml)、[说明](../../astrbot_plugin_access_gate/README.md)、[指令源码](../../astrbot_plugin_access_gate/main.py) |
| API 钱包余额 | `astrbot_plugin_wallet_balance` | 0.2.1 | 启用 0.2.1 | 开启 | [元数据](../../astrbot_plugin_wallet_balance/metadata.yaml)、[说明](../../astrbot_plugin_wallet_balance/README.md)、[指令源码](../../astrbot_plugin_wallet_balance/main.py) |
| 插件更新动态 | `astrbot_plugin_githook` | 0.3.0 | 启用 0.3.0 | 开启 | [元数据](../../astrbot_plugin_githook/metadata.yaml)、[说明](../../astrbot_plugin_githook/README.md)、[指令源码](../../astrbot_plugin_githook/main.py) |
| 本群帮助 | `astrbot_plugin_custom_help` | 2.3.0 | 启用 1.0.0 | 开启 | [元数据](../../astrbot_plugin_custom_help/metadata.yaml)、[说明](../../astrbot_plugin_custom_help/README.md)、[指令源码](../../astrbot_plugin_custom_help/main.py) |
| 使用统计 | `astrbot_plugin_usage_stats` | 0.2.0 | 未出现 | 关闭 | [元数据](../../astrbot_plugin_usage_stats/metadata.yaml)、[说明](../../astrbot_plugin_usage_stats/README.md)、[指令源码](../../astrbot_plugin_usage_stats/main.py) |
| 可可子人格管理 | `astrbot_plugin_persona_manager` | 0.4.0 | 停用 0.4.0 | 关闭 | [元数据](../../astrbot_plugin_persona_manager/metadata.yaml)、[说明](../../astrbot_plugin_persona_manager/README.md)、[指令源码](../../astrbot_plugin_persona_manager/main.py) |
| 星轨神谕 · 星图 | `astrbot_plugin_astro_oracle` | 0.1.5 | 停用 0.1.5 | 关闭 | [元数据](../../astrbot_plugin_astro_oracle/metadata.yaml)、[说明](../../astrbot_plugin_astro_oracle/README.md)、[指令源码](../../astrbot_plugin_astro_oracle/main.py) |
| Grok AI 助手 | `astrbot_plugin_grok_uuapi` | 1.0.0 | 未出现 | 关闭 | [元数据](../../astrbot_plugin_grok_uuapi/metadata.yaml)、[说明](../../astrbot_plugin_grok_uuapi/README.md)、[指令源码](../../astrbot_plugin_grok_uuapi/main.py) |
| 调用汇总分析 | `astrbot_plugin_analysis` | 1.1.0 | 未出现 | 关闭 | [元数据](../../astrbot_plugin_analysis/metadata.yaml)、[说明](../../astrbot_plugin_analysis/README.md)、[指令源码](../../astrbot_plugin_analysis/main.py) |

重复目录来源：[junjunget 元数据](../../astrbot_plugin_junjunget/metadata.yaml)。生图内容另核对 [生图功能说明](../../astrbot_plugin_img_gener/AGENTS.md)；紫微版本范围另核对 [紫微维护约定](../../astrbot_plugin_ziwei/AGENTS.md)。

## 初始文字说明

以下为种子内容的可读快照；实际帮助图使用管理页面保存的说明与所选群顺序。

### 太鼓 · 今日人品

每日 RP、历史统计与本群排行榜。

```text
/rp：抽取或查看今日人品，同一用户同一天结果相同。
/rp 积分：查看本人当前积分，不重新抽签。
/rp 统计：最近 30 条 RP 曲线及历史等级统计。
/rp 历史 7：查看最近 7 条记录；也可填写日期，例如 /rp 历史 2026-08-01。
/rp 排行榜 20：查看本群今日前 20 名。
/rp help：查看完整帮助。
签到积分以门禁积分插件的实际设置为准；历史和排行榜不会补抽缺失日期。管理员可使用 /rp 存储 查看占用，/rp 清理 天数 清理旧数据。
```

### RTLink · 太鼓成绩

成绩同步、Rating 画像、练习建议与段位查询。

```text
先私聊绑定：/rtlink bind <apikey> <player_id> [server]，或 /rtlink bind sakura <token>。请勿在群聊发送密钥。
/rtlink：刷新成绩并生成个人画像；/rtlink profile：读取有效缓存画像。
/rtlink source：查看来源；后加 kinoko 或 sakura 切换；/rtlink unbind：解绑当前来源。
/rtlink score 鬼夏祭：查询指定曲目成绩。
/rtlink rating：实力画像；/rtlink progress：配置评分与历史曲线。
/rtlink weakness：弱项和练习建议；/rtlink improve 紫雅 鬼：评价提升建议。
/rtlink dan 2025 十段：段位课题曲与条件。
/rtlink alias <ID或曲名> <别名>：申请歌曲别名。
/rtlink update：强制同步；/rtlink help：完整帮助；/rtlink about：插件信息。
```

### 六爻起卦

六爻排盘、AI 解读、额度查询和卦例反馈。

```text
/六爻：查看帮助。
/六爻 这个项目能否按期完成：围绕具体事情起卦；也可用 /起卦 六爻 问题。
/额度：查看今日余量、有效反馈与恢复时间。
/六爻反馈：查看待反馈卦例；/六爻反馈 列表 2：翻页。
/六爻反馈 1：回看指定编号；/六爻反馈 1 项目已经按期交付：提交实际结果。仅一条待反馈时可省略编号。
/ping：检测当前模型，会发送一次模型请求，不扣起卦额度。
空泛或不成立的问题不调用 AI 解卦；有效解读成功后才计入每日或赠送额度。
群主、群管理员或 AstrBot 管理员可用 /六爻 开、/六爻 关 设置本群；/六爻test 问题 仅限 AstrBot 管理员诊断。
```

### 五行数字卦

提供具体问题和五个数字，生成五行数字卦图。

```text
/数字卦 13254 这次求职能否成功
也可使用：/数字卦 这次求职能否成功 | 1 3 2 5 4
手动根气：/数字卦 合同能否顺利签下 | 13254 | 金
请提供真实、具体的问题与恰好五个数字；只有数字不会起卦。省略根气时由 AI 根据问题选择根气，排盘和解卦由程序完成。
AI 取根气按本群配置限次；明确手动填写水、火、木、金、土之一时不调用 AI。
同一用户同一问题连续三次死卦后停止继续问该事项；数字卦与六爻的记录和额度相互独立。
```

### 紫微斗数排盘

本命盘、个人绑定、流年大运和人生图谱。

```text
/紫薇：查看图片帮助；/紫薇帮助文字：完整文字帮助。
/紫微 199006150830 男：按出生年月日时分排盘（虚构示例，请换成自己的资料）。
/紫微 农历 199005230830 男：农历排盘。
/紫微 绑定 199006150830 男：绑定本命盘；/我的命盘：查看。
/紫微 流年 2026：绑定命盘的流年；/紫微 大运 2：第 2 大运。
/紫微 换绑 199207201430 女：重新填写资料换绑；/紫微 解绑：解除绑定。
/人生：用已绑定命盘生成图谱，也可另填出生资料。
常用选项：主题=白天、主题=夜间、文字；完整用法见插件帮助。
须在已开启的群内使用；群主、群管理员或 AstrBot 管理员可用 /紫微 开启、/紫微 关闭，/紫微 状态 查看开关。当前版本不提供 AI 看盘。
```

### 干支纪时

当前四柱、个人日运、生日绑定与群日报。

```text
/干支：查看当前四柱图片；已绑定时附个人日运与时辰宜忌。
/干支 辛巳：临时按日柱查看；也可填写单个日主，如 /干支 辛。
/干支 20010319：临时按阳历生日查看（虚构示例）。
/干支 绑定 20010319：绑定阳历生日；/干支 绑定 辛巳：直接绑定日柱。
/干支 我的：查看绑定信息；/干支 解绑：删除绑定。
/干支 help：完整帮助。
/干支日报 状态：查看本群日报；群主、群管理员或 AstrBot 管理员可用 /干支日报 开、/干支日报 关 设置订阅。
生日只接受阳历；临时查询不覆盖绑定。
```

### AI 生图与动图

文字生图、GIF、参考图、永久图库与随机／指定编号裁切拼图。

```text
/生图 雨后的车站，温暖插画风：生成静态图片；也可用 /绘图、/draw。
/生动图 眨眼的小猫：生成 GIF；默认 512×512、16 帧、每帧 40ms。
静态图和 GIF 均可直接附图或回复图片作为参考，也可直接告诉 AI 你的需求。
/生图人物：查看可用人物；/生图参考图：查看自己的本体参考图。
/生图参考图 设置：同时发送或引用恰好一张图片，替换自己的参考图。
/生图状态：查看队列、进度、最近结果、余量与冷却。
/生图历史：查看图库说明；/生图历史 123：按编号查看原图及详情。
/生图历史 随机：随机单图；/生图历史 随机 4：整图宫格，数量 1～9。
/随机拼图：随机两张图，等高后各取左、右半幅拼接。
/随机拼图 4：四宫格裁切；支持 2～20 张，偶数宫格、奇数饼图扇形。
/拼图 233 123：按图库编号裁切，233 左半、123 右半；2～20 个编号用空格分隔，无需方括号。
/拼图 233 123 456：按输入顺序拼成三个扇形；四个编号为四宫格，与随机拼图规则一致。
/画廊：本人最近 20 张；/画廊 10：最近 10 张；/画廊 -5：从最近第 5 张起取最多 20 张。
/画廊 [123 151 488]：按编号和顺序展示完整图片，最多 20 项，方括号须保留。
拼图与画廊只在本地处理，不占生图额度；GIF 仅取首帧，查看完整动图请用 /生图历史 编号。
生图任务受理后在后台生成，请按任务号核对结果。管理员可在生图管理页配置参数、管理图库与参考图。
```

### 思考气泡

把指定文字排进普通或可可子思考气泡。

```text
/think 今天也要好好打鼓！：生成普通思考气泡。
/可可子思考 我在想今天先练哪首歌：生成可可子思考气泡。
普通模板别名：/想法、/t。
可可子模板别名：/可可子think、/可可子t、/kkzt、/kt。
指令后填写要展示的文字，程序自动换行并调整字号。
```

### 投喂与赞助

发送可可子的投喂赞助卡片。

```text
/投喂：查看赞助卡片。
管理员可在插件的赞助设置页面修改标题、二维码、角色图及整张底图，裁切图片、预览效果或恢复默认。
```

### QQ 群入群欢迎

新成员入群时自动发送图文欢迎。

```text
新人加入群聊后自动发送欢迎图片与文字，普通成员无需手动触发。
以下操作限群主、群管理员或 AstrBot 管理员：
/welcome on：开启本群欢迎；/welcome off：关闭。
/welcome set 欢迎 {nickname} 加入我们！：设置本群专属欢迎词。
/welcome test：预览当前群的欢迎消息。
也支持中文子命令 开、关、设置、测试。欢迎词可使用 {nickname}、{user_id}、{group_id}；管理员可在插件设置中配置图片和全局默认欢迎词。
```

### 门禁与积分

群聊访问、唤醒规则、积分与聊天预算管理。

```text
/积分：查看本人当前积分；/rp 积分 查询同一账本。
/rp 可按当前配置领取签到积分；戳一戳机器人可按配置获得随机积分。是否发奖、奖励次数和金额以实际设置为准。
个人积分模式按个人余额及预算控制聊天；全局积分模式共享日月预算，不扣个人积分，也不发 RP 签到积分。
群白名单、开放时段与唤醒规则由管理员设置。帮助中的功能仍须符合对应插件权限和额度。
AstrBot 管理员：/accessgate status 查看状态；/accessgate help 查看管理用法；积分与预算、流水可在插件管理页编辑和查询。
```

### API 钱包余额

管理员查询 API 钱包与群 Token 消耗。

```text
以下查询限 AstrBot 管理员，普通群管理员不具备该权限。
/余额：查询已配置 API 账户的钱包余额，默认返回角色气泡图片；兼容 /钱包余额、/余额查询、/wallet。
/群消耗汇总：今日、累计总计与各群列表。
/群消耗汇总 今日：今日用量；/群消耗汇总 累计：累计用量。
/群消耗汇总 2026-10-29：指定北京日期；/群消耗汇总 今日 2：第 2 页。
费用按可识别的实际 Token 与插件价表估算；未返回的用量会标为未知，估算不等同于服务商账单。
```

### 插件更新动态

查询插件安装信息、提交历史及群更新推送。

```text
/githook 列表：查看已发现插件及推送开关。
/githook 六爻：查询指定插件的安装或登记信息。
/githook 历史：全部受管插件最近 30 条提交。
/githook 历史 六爻：指定插件提交；后加 页 2 翻页，也可加 61-90 指定范围。
/githook 历史 六爻 2026-09-20：查询某日提交。
/githook 状态：本群推送状态；/githook 帮助：完整帮助。
只有 AstrBot 管理员可用 /githook 开、/githook 关 设置本群推送；仓库推送也需在配置中单独开启。普通用户可主动查询，推送不会自动升级插件。
```

### 本群帮助

查看本群已选择的插件说明。

```text
/help 或 /帮助：查看当前群绑定模板的插件帮助图。
管理员为本群配置后，可单独 @机器人、发送设定的点名名称（默认可可子）或戳机器人查看相同帮助；以当前群实际开启的入口为准。
管理员可创建和复制模板，编辑插件说明与表头清单、调整顺序，勾选应用的群并生成预览。
帮助展示开关只决定本图包含哪些说明；插件本身的启用、群授权、额度和权限仍由各插件管理。
```

### 使用统计

个人指令和 Token 用量，以及本群排行榜。

```text
/使用统计：本人累计指令次数、模型调用、Token 与常用时段。
/使用统计 指令 1：按指令查看第 1 页；/使用统计 模型 1：按模型查看明细。
/使用排行：本群累计指令次数排行及自己的名次。
/token：本人累计及今日 Token、调用次数和统计开始时间。
/token排行：本群累计已知 Token 排行及自己的名次。
个人汇总覆盖同一机器人下自己的群聊与私聊；群榜仅统计当前群。数据从插件启用后累计，缺失用量不会被当成零。
```

### 可可子人格管理

管理员配置群内表达学习、互动记忆与核心人格。

```text
此插件没有独立聊天指令，在管理员明确开启的 QQ 群中学习表达并积累互动记忆。
管理员在 AstrBot 的人格管理页面选择群聊，分别开启旁听学梗、互动记忆或允许使用全局梗，并设置预算、学习模型和方向。
页面可编辑核心人格，查看与纠正人物记忆和时间线，停用群表达或回滚。新发现的群默认不学习；私聊不采集、不检索、不学习。
```

### 星轨神谕 · 星图

根据时间与地点生成真实天体双半球星图。

```text
/星图：当前时刻、默认北京的星图。
/星图 北京 20250102：指定地点和公历日期；/星图 200010100100：指定年月日时分。
/星图 30.25°N 120.5°E：指定经纬度，也可使用 纬度,经度。
/星图 help：查看完整帮助；别名为 /xingtu、/xt、/star。
未填写时间时使用当前时刻；仅日期时，缺失时分秒默认补为 08:00:00，可由管理员配置。
/紫薇星图 北京 20261012200000：真实天球与传统十二宫的研究对照图；也支持 /紫微星图。该对照不是紫微斗数插件的个人命盘。
```

### Grok AI 助手

Grok 生图、视频、联网对话及额度查询。

```text
/grok生图 一只戴宇航头盔的橘猫：生成图片；附带或引用图片时可进行图生图。
/grok生图 4 3:2 日落海滩：指定数量与尺寸。
/grok视频 10 夜晚海边的慢镜头：生成视频，可附带参考图片。
/grok 今天的 AI 新闻有哪些：与 Grok 对话。
/grok额度：查看额度、冷却和并发；/grok模型：查看可见模型；/grok帮助：完整说明。
生成任务受理后在后台处理；权限、白名单、可用模型和限额以管理员配置为准，默认仅管理员可用。
AstrBot 管理员可用 /grok重置 <QQ号或群号> 重置指定额度，all 表示全部。
```

### 调用汇总分析

管理员汇总机器人调用，生成报告与群聊复盘。

```text
管理员指令：
/analysis report 最近7天 当前 pdf：生成当前群调用汇总报告。
/analysis digest 最近3天 当前 bug,报错 txt：围绕关注点精读群聊并复盘。
/analysis groups：查看记录过的群；/analysis status：查看记录与存储状态。
/analysis export 最近7天 当前：导出原始 JSONL 记录，不调用模型。
/analysis record on、off、reset：临时恢复、暂停或重置本群记录策略。
/analysis help：完整说明；主指令别名为 /汇总、/调用汇总。
报告支持 word、pdf、md、txt；省略群范围会选择全部已记录群，请按实际需要指定 当前 或群号。
```

## 维护核对

更新插件功能时先核对实际命令入口和权限，再维护种子。新增目录不能仅凭目录名重复生成运行标识；没有部署证据的本地插件默认关闭。更改帮助展示不会安装、启用、停用或授权对应功能。

## 2026-11-10 样式读取

说明文字沿用本文核对范围。v2.1.0 新增读取已安装六爻、紫微和 RTLink 帮助样式；只更新本插件版本，不自动改写已保存说明。原生风格来源、资源要求和回退规则见 [README](../README.md#帮助图片风格)。


## 2026-11-11 帮助模板与快捷入口

自定义帮助 v2.3.0 改为模板绑定群聊，加入可组合的空 @、独立点名（名称可编辑）和戳机器人入口；按群开启快捷帮助。六爻 v0.33.3 移除旧通用 @ 兜底，门禁 v2.4.2 在白名单、休息及戳一戳积分处理后衔接帮助。只更新本次涉及插件的本地版本；附件部署状态仍保留原快照，旧六爻群号不会自动启用新入口。
