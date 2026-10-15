# 牛子PK（Dicky-PK）

移植自 NoneBot 插件 (作者已将仓库归档) 0.7.1（原作者 月ヶ瀬）的群聊小游戏：
注册牛子、pk、🔒、打胶、看他牛子、牛子排名、牛子转生、牛子成就、牛子仙境修炼、牛友系统。

- 插件 ID：`octmicy.dicky-pk`
- 版本：`1.0.0`（游戏内版本字符串仍为原版 `2.6.5`，两者无关，见下"已知偏差"）
- 依赖：**零第三方依赖**（纯标准库 + MaiBot Plugin SDK）

---

## 1. 指令表

指令命中顺序 = Host 侧**方法名字母序**（与源码书写顺序无关），重叠 pattern 已用否定先行断言解耦，
无需关心顺序。带 `@` 的指令必须 at 一个用户。

### 1.1 游戏指令

| 指令 | 别名 / 写法 | at | 聊天范围 | 权限 |
| --- | --- | --- | --- | --- |
| `注册牛子` | — | 可选 | 仅群聊 | public |
| `牛子` | 兜底指令；`牛子 排名`、`牛子 转生` 等带空格写法会归一化后走对应指令 | 可选 | 群聊 + 私聊只读 | public |
| `牛子帮助` | — | 可选 | 群聊 + 私聊只读 | public |
| `牛子排名` | `牛子排行` | 可选 | 群聊 + 私聊只读 | public |
| `牛子成就` | — | 可选 | 群聊 + 私聊只读 | public |
| `牛友` | `牛子好友`、`牛子朋友` | 可选 | 群聊 + 私聊只读 | public |
| `牛子转生` | — | 可选 | 仅群聊 | public |
| `牛子仙境` | — | 可选 | 仅群聊 | public |
| `牛子修炼` | `牛子练功`、`牛子修仙` | 可选 | 仅群聊 | public |
| `关注牛子` | `添加牛友`、`添加朋友` | **必须** | 仅群聊 | public |
| `取关牛子` | `删除牛友`、`删除朋友` | **必须** | 仅群聊 | public |
| `看他牛子` | `看看牛子` | **必须** | 仅群聊 | public |
| `pk` | — | **必须** | 仅群聊 | public |
| `🔒我` | `suo我`、`嗦我`、`锁我` | 可选 | 仅群聊 | public |
| `🔒` | `suo`、`嗦`、`锁`（`X我` 归 `🔒我`） | 可选 | 仅群聊 | public |
| `打胶` | — | 可选 | 仅群聊 | public |

> `🔒` / `suo` / `嗦` / `锁` 四个前缀等价，`X我` 一律归 `🔒我`，`X`（后不接"我"）归 `🔒`；
> 引擎内部（`game/main.py`）对这些关键词是前缀模糊匹配，因此 `锁我 @张三` 这类带 at 的
> "锁自己"写法实际会走"锁对方"分支——与原版行为一致（见 §5 偏差 26）。

### 1.2 开关指令（operator）

| 指令 | 说明 | at | 聊天范围 | 权限 |
| --- | --- | --- | --- | --- |
| `开启牛子秘境` | 牛子秘境总开关；群聊中同时在本群启用牛子pk | 可选 | 群聊 + 私聊 | **operator** |
| `关闭牛子秘境` | 总开关关闭，并清空已启用群列表 | 可选 | 群聊 + 私聊 | **operator** |
| `启用牛子pk` / `开启牛子pk` / `启用dicky-pk` / `开启dicky-pk` | 在本群启用牛子pk | 可选 | 仅群聊 | **operator** |
| `禁用牛子pk` / `关闭牛子pk` / `禁用dicky-pk` / `关闭dicky-pk` | 在本群禁用牛子pk | 可选 | 仅群聊 | **operator** |

---

## 2. 权限说明

- 全部游戏指令：`public`（任何人可用，但需过门禁，见下）。
- 四个开关指令：`permission="operator"`，由 Host 命令链校验（`chat/message_receive/bot.py`），
  非 operator 会被拦截并提示，不会进入插件逻辑。

### 2.1 门禁规则（两层）

1. **插件层**：`[plugin].enabled = true`（默认 true）——由 Host 决定插件是否激活。
2. **游戏层**（`game/enable.py`）：
   - 群聊指令：牛子秘境总开关 `all=true` **且**本群在启用列表中，才放行；
   - 私聊只读指令（牛子 / 牛子排名 / 牛子成就 / 牛友 / 牛子帮助）：仅要求总开关 `all=true`；
   - 私聊中其他一切读写指令：统一回复
     `该指令仅在和机器人的群聊中使用（私聊可查询：牛子、牛子排名、牛子成就、牛友、牛子帮助）`。

默认状态 `{"all": false, "group": []}`——装好后默认不开放，需 operator 先 `开启牛子秘境`
（原版 NoneBot 版同样默认关闭）。游戏未开启时指令不回复任何内容，消息继续走 AI。

### 2.2 典型上线步骤

```
operator: 开启牛子秘境        → "牛子秘境已开启.\n已在本群启用牛子pk"
（若秘境此前已开，单独开某群）
operator: 启用牛子pk          → "已启用群聊小游戏: Dicky-PK"
群友:     注册牛子            → 分配随机长度
群友:     pk @某人 / 打胶 @某人 / 🔒我 / 看他牛子 @某人 ...
```

---

## 3. 配置说明（`config.toml`）

配置为全量强类型模型 `DickyPKConfig`（`config.py`，共 80 个字段，9 个节），
默认值与原版 `src/config.json` **逐一相等**（已用 OneKey env python 逐项深比较通过）。
`config.toml` 与模型默认值等价，WebUI 配置页按节渲染。

| 节 | 模型类 | 字段数 | 含义 |
| --- | --- | --- | --- |
| `[plugin]` | `PluginSectionConfig` | 2 | `enabled`（宿主插件开关）、`config_version` |
| `[basic]` | `BasicConfig` | 12 | 注册长度随机范围、🔒/pk/打胶的每日上限与 CD 触发（时间 + 比例） |
| `[lock]` | `LockConfig` | 8 | 🔒自己惩罚与增益、🔒他人增益、对"强者"的特殊惩罚 |
| `[glue]` | `GlueConfig` | 8 | 打胶增益、给自己打胶的失败率与惩罚、给别人打胶的破坏几率与惩罚 |
| `[pk]` | `PKConfig` | 8 | pk 不稳定范围、胜率边缘、胜负奖惩、弱者保护长度、排行榜人数 |
| `[rebirth]` | `RebirthConfig` + `RebirthLevelConfig` | 8 | 转生等级列表（5 级，`level` 为唯一 id，**勿改已有值**） |
| `[badge]` | `BadgeConfig` + `BadgeCategoryConfig` | 8 | 成就列表（`id` 为唯一 id，**勿改已有值**；`conditions`/`additions` 为编码字符串列表） |
| `[farm]` | `FarmConfig` + `FarmCostStageConfig` | 10 | 仙境开放开始时间/时长、修炼阶段、收益（`reward_min/reward_max/reward_base`） |
| `[friends]` | `FriendsConfig` | 12 | 好友上限、朋友费与手续费、牛友对 pk/🔒/打胶的加成（`addition_*_plus_base/share`） |

说明：

- `basic/lock/glue/pk` 四节在引擎内部被**平铺到顶层**，`rebirth/badge/farm/friends` 四节保持嵌套，
  键形与原版 `config.json` 完全一致（`game/config.py: flatten_config` 负责把拍平的标量/编码字符串
  还原成原版嵌套 dict，游戏逻辑零改动）。
- 时间格式串为 `AhBm`（如 `10h`、`1h20m`、`30m`）；仙境开始时间为 24 小时制 `hh:mm`。
- 成就条件每条编码为 `"字段名|表达式"`（如 `pk_win_count|>=50`，只支持 `>` 和 `>=`）；
  加成每条编码为 `"字段名|表达式1,表达式2"`（如 `pk_weight|10%,1`，`%` 结尾为比例，纯数字为固定值）。
  WebUI 配置表单只支持一层对象数组且元素仅限标量，故用编码字符串承载 字段->表达式 映射。
- **热更新**：修改 `config.toml` 保存后，`on_config_update` 会重建扁平配置桥并调用
  `BadgeSystem/FarmSystem/FriendsSystem` 的 `reset_cache()`，新参数立即生效，无需重启。
- 废弃键 `_pk_unstable_range`（v2.4.3 起弃用）未迁移，其 `deprecated_tips` 一并删除。

---

## 4. 部署

### 4.1 部署路径

```
C:\Users\octmicy\AppData\Roaming\MaiBotOneKeyDesktop\0163381a22cb\modules\MaiBot\plugins\dicky_pk\
```

即 `<MaiBot 模块根>\plugins\dicky_pk\`——**整个 `dicky_pk/` 目录拷入**（含 `config.toml`、
`_manifest.json`、`game/` 子包）。

### 4.2 数据目录

```
<MaiBot 模块根>\data\plugins\octmicy.dicky-pk\
├── data.sqlite      六张表：users / info / rebirth / badge / farm / friends
└── enable.json      牛子秘境总开关 + 已启用群列表
```

路径来自 `ctx.paths.data_dir`（`maibot_sdk/context.py`），不迁移任何 NoneBot 旧数据
（原版 `data/chinchin_pk/data-v2/data.sqlite` 不读取、不复制）。

### 4.3 部署方法

1. 停写主程序相关配置（本插件不依赖改主程序任何文件）。
2. 复制目录：
   ```bash
   cp -r D:/workdoc/plugin/maibot-plugin-dicky-pk/dicky_pk \
         "C:/Users/octmicy/AppData/Roaming/MaiBotOneKeyDesktop/0163381a22cb/modules/MaiBot/plugins/"
   ```
   （Windows 下等价的 `robocopy` / `xcopy /E /I` 亦可；不要遗漏 `config.toml`。）
3. 在 OneKey 中重载插件 / 重启主程序，使 Runner 重新 `collect_components`。
4. WebUI → 插件配置 → 牛子PK：确认 9 个配置节渲染正常。
5. operator 在群里发送 `开启牛子秘境` → `启用牛子pk` → `注册牛子` 开始游戏。

### 4.4 环境要求

| 项 | 版本 |
| --- | --- |
| Host | ≥ 1.3.0（`_manifest.json: host_application.min_version`） |
| MaiBot Plugin SDK | ≥ 2.6.0（`_manifest.json: sdk.min_version`） |
| Python | 3.12 |
| capabilities | `send.text` |

---

## 5. 目录结构

```
dicky_pk/
├── __init__.py           __version__ = "1.0.0"
├── _manifest.json        id=octmicy.dicky-pk，capabilities=["send.text"]
├── config.py             DickyPKConfig 全量强类型配置模型（88 字段 / 9 节）
├── config.toml           与模型默认值等价的配置文件（可改，热更新生效）
├── plugin.py             DickyPKPlugin：生命周期 + 全部 @Command 注册
├── README.md             本文件
└── game/                 游戏逻辑（全部同步代码）
    ├── config.py         Config 扁平桥 + flatten_config
    ├── config_parser.py  TimeParser（逐字移植）
    ├── constants.py      OpFrom / FarmConst / TimeConst
    ├── db.py             六张表 + 复合键（init/lazy_init/close_database）
    ├── enable.py         牛子秘境群开关（enable.json）
    ├── utils.py          join/ArrowUtil/NumberUtils/Random 等（arrow→datetime）
    ├── cd.py             CD_Check
    ├── badge.py          BadgeSystem（+reset_cache）
    ├── badge_parser.py   BadgeSystem_Parser
    ├── rebirth.py        RebirthSystem（+reset_cache）
    ├── rebirth_view.py   RebirthSystem_View
    ├── farm.py           FarmSystem（+reset_cache）
    ├── friends.py        FriendsSystem（+reset_cache）
    └── main.py           message_processor + 全部 Chinchin_* 类
```

import 方向（防循环，与原版一致）：`main -> db/config/cd/rebirth/badge/farm/friends/constants/utils`；
`db -> config/utils/constants`（禁止 import main）。
