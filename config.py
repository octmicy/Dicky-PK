"""牛子PK 插件全量强类型配置模型。

默认值与原版 nonebot-plugin-dicky-pk 的 ``src/config.json`` 逐一相等（硬约束）。
原 ``config.json`` 中以 ``##`` 开头的注释键不进入模型，其说明内容写入对应 ``Field`` 的
``description``；已废弃的 ``_pk_unstable_range``（v2.4.3 起弃用）不迁移。

结构总览（与 ``game/config.py`` 的 ``flatten_config`` 输出键形一一对应）：

- ``plugin``   ：宿主保留节（enabled / config_version）
- ``basic``    ：注册长度、每日上限、CD 触发等基础参数（扁平桥中平铺到顶层）
- ``lock``     ：🔒 相关参数（扁平桥中平铺到顶层）
- ``glue``     ：打胶相关参数（扁平桥中平铺到顶层）
- ``pk``       ：pk 相关参数（扁平桥中平铺到顶层）
- ``rebirth``  ：转生等级列表
- ``badge``    ：成就列表
- ``farm``     ：牛子仙境配置
- ``friends``  ：牛友配置
"""

from __future__ import annotations

from maibot_sdk import Field, PluginConfigBase


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置（宿主保留节，勿删字段）。"""

    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0

    enabled: bool = Field(
        default=True,
        description="是否启用插件",
        json_schema_extra={"label": "启用插件", "hint": "关闭后插件不会参与任何消息处理"},
    )
    config_version: str = Field(
        default="1.0.0",
        description="配置版本",
        json_schema_extra={"label": "配置版本", "hint": "配置结构版本号，升级插件时用于迁移"},
    )


class BasicConfig(PluginConfigBase):
    """基础配置：注册长度、每日上限与 CD 触发。"""

    __ui_label__ = "基础"
    __ui_icon__ = "ruler"
    __ui_order__ = 1

    new_chinchin_length_random_min: int = Field(
        default=8,
        description="注册新牛子的长度范围最小值",
        json_schema_extra={"label": "新牛子长度最小值", "hint": "注册牛子时的随机长度下限（cm）"},
    )
    new_chinchin_length_random_max: int = Field(
        default=15,
        description="注册新牛子的长度范围最大值",
        json_schema_extra={"label": "新牛子长度最大值", "hint": "注册牛子时的随机长度上限（cm）"},
    )
    lock_me_chinchin_min: int = Field(
        default=20,
        description="🔒自己需要的最小长度",
        json_schema_extra={"label": "🔒自己最小长度", "hint": "长度不足时🔒自己会受到惩罚"},
    )
    lock_daily_max: int = Field(
        default=36,
        description="每天🔒的上限次数，包括🔒自己和别人",
        json_schema_extra={"label": "🔒每日上限", "hint": "每天🔒的上限次数，包括🔒自己和别人"},
    )
    cd_trigger_lock_time: int = Field(
        default=60,
        description="一旦🔒过了 rate 百分比的数量，之后每次🔒就需要等 time 分钟的 cd",
        json_schema_extra={"label": "🔒 CD 时间", "hint": "触发 CD 后每次🔒需要等待的分钟数"},
    )
    cd_trigger_lock_rate: float = Field(
        default=0.5,
        description="一旦🔒过了 rate（[0, 1]）百分比的数量，之后每次🔒就需要等 time 分钟的 cd",
        json_schema_extra={"label": "🔒 CD 触发比例", "hint": "取值 [0, 1]，超过该比例的日次数后进入 CD"},
    )
    pk_daily_max: int = Field(
        default=36,
        description="每天pk的上限次数，包括pk自己和别人",
        json_schema_extra={"label": "pk每日上限", "hint": "每天pk的上限次数，包括pk自己和别人"},
    )
    cd_trigger_pk_time: int = Field(
        default=60,
        description="一旦pk过了 rate 百分比的数量，之后每次pk就需要等 time 分钟的 cd",
        json_schema_extra={"label": "pk CD 时间", "hint": "触发 CD 后每次pk需要等待的分钟数"},
    )
    cd_trigger_pk_rate: float = Field(
        default=0.5,
        description="一旦pk过了 rate（[0, 1]）百分比的数量，之后每次pk就需要等 time 分钟的 cd",
        json_schema_extra={"label": "pk CD 触发比例", "hint": "取值 [0, 1]，超过该比例的日次数后进入 CD"},
    )
    glue_daily_max: int = Field(
        default=36,
        description="每天打胶的上限次数，包括打胶自己和别人",
        json_schema_extra={"label": "打胶每日上限", "hint": "每天打胶的上限次数，包括打胶自己和别人"},
    )
    cd_trigger_glue_time: int = Field(
        default=60,
        description="一旦打胶过了 rate 百分比的数量，之后每次打胶就需要等 time 分钟的 cd",
        json_schema_extra={"label": "打胶 CD 时间", "hint": "触发 CD 后每次打胶需要等待的分钟数"},
    )
    cd_trigger_glue_rate: float = Field(
        default=0.5,
        description="一旦打胶过了 rate（[0, 1]）百分比的数量，之后每次打胶就需要等 time 分钟的 cd",
        json_schema_extra={"label": "打胶 CD 触发比例", "hint": "取值 [0, 1]，超过该比例的日次数后进入 CD"},
    )


class LockConfig(PluginConfigBase):
    """🔒 相关配置。"""

    __ui_label__ = "🔒 锁"
    __ui_icon__ = "lock"
    __ui_order__ = 2

    lock_me_negative_prob: float = Field(
        default=0.7,
        description="🔒自己长度不够的处罚几率 [0, 1]",
        json_schema_extra={"label": "🔒自己失败几率", "hint": "🔒自己长度不够时的处罚几率，取值 [0, 1]"},
    )
    lock_me_negative_min: float = Field(
        default=0.1,
        description="🔒自己长度不够的处罚范围最小值",
        json_schema_extra={"label": "🔒自己惩罚最小值", "hint": "🔒自己长度不够时缩短长度的下限（cm）"},
    )
    lock_me_negative_max: float = Field(
        default=1,
        description="🔒自己长度不够的处罚范围最大值",
        json_schema_extra={"label": "🔒自己惩罚最大值", "hint": "🔒自己长度不够时缩短长度的上限（cm）"},
    )
    lock_plus_min: float = Field(
        default=0.1,
        description="🔒牛子的增加长度范围最小值，包括🔒自己和别人",
        json_schema_extra={"label": "🔒增益最小值", "hint": "🔒带来增长的下限（cm），包括🔒自己和别人"},
    )
    lock_plus_max: float = Field(
        default=1,
        description="🔒牛子的增加长度范围最大值，包括🔒自己和别人",
        json_schema_extra={"label": "🔒增益最大值", "hint": "🔒带来增长的上限（cm），包括🔒自己和别人"},
    )
    lock_me_negative_prob_with_strong_person: float = Field(
        default=0.2,
        description="满足🔒自己的长度后，回报高，但有概率失败得到大额惩罚",
        json_schema_extra={"label": "强者制裁几率", "hint": "长度达标后🔒自己仍可能爆炸的几率 [0, 1]"},
    )
    lock_me_negative_with_strong_person_min: float = Field(
        default=2,
        description="满足🔒自己的长度后爆炸惩罚的最小值",
        json_schema_extra={"label": "强者制裁最小值", "hint": "爆炸时缩短长度的下限（cm）"},
    )
    lock_me_negative_with_strong_person_max: float = Field(
        default=5,
        description="满足🔒自己的长度后爆炸惩罚的最大值",
        json_schema_extra={"label": "强者制裁最大值", "hint": "爆炸时缩短长度的上限（cm）"},
    )


class GlueConfig(PluginConfigBase):
    """打胶相关配置。"""

    __ui_label__ = "打胶"
    __ui_icon__ = "droplets"
    __ui_order__ = 3

    glue_plus_min: float = Field(
        default=0.5,
        description="打胶增加长度的范围最小值",
        json_schema_extra={"label": "打胶增益最小值", "hint": "打胶成功时增长的下限（cm）"},
    )
    glue_plus_max: float = Field(
        default=1.5,
        description="打胶增加长度的范围最大值",
        json_schema_extra={"label": "打胶增益最大值", "hint": "打胶成功时增长的上限（cm）"},
    )
    glue_self_negative_prob: float = Field(
        default=0.2,
        description="打胶自己失败的概率 [0, 1]",
        json_schema_extra={"label": "自己打胶失败率", "hint": "给自己打胶时失败缩短的几率 [0, 1]"},
    )
    glue_self_negative_min: float = Field(
        default=0.1,
        description="打胶自己失败时缩短长度的最小值",
        json_schema_extra={"label": "自己打胶惩罚最小值", "hint": "给自己打胶失败缩短的下限（cm）"},
    )
    glue_self_negative_max: float = Field(
        default=0.5,
        description="打胶自己失败时缩短长度的最大值",
        json_schema_extra={"label": "自己打胶惩罚最大值", "hint": "给自己打胶失败缩短的上限（cm）"},
    )
    glue_negative_prob: float = Field(
        default=0.3,
        description="给别人打胶破坏对方牛子的几率 [0, 1]",
        json_schema_extra={"label": "打胶破坏几率", "hint": "给别人打胶时破坏对方牛子的几率 [0, 1]"},
    )
    glue_negative_min: float = Field(
        default=0.1,
        description="给别人打胶失败的话，对方牛子减小范围的最小值",
        json_schema_extra={"label": "打胶破坏最小值", "hint": "打胶破坏时对方缩短的下限（cm）"},
    )
    glue_negative_max: float = Field(
        default=1,
        description="给别人打胶失败的话，对方牛子减小范围的最大值",
        json_schema_extra={"label": "打胶破坏最大值", "hint": "打胶破坏时对方缩短的上限（cm）"},
    )


class PKConfig(PluginConfigBase):
    """pk 相关配置。"""

    __ui_label__ = "PK"
    __ui_icon__ = "swords"
    __ui_order__ = 4

    pk_unstable_range_v2: float = Field(
        default=1,
        description=(
            "取值范围 [0, ∞)，pk时没有绝对实力差距的范围。"
            "可以设定为 0.1, 1, 1.1 等（1.1 是 110%），比如 1 时，50cm 允许挑战 100cm 以内的，"
            "两者差的越多，越难赢，挑战 100cm+ 的存在绝对实力差距，无法获胜"
        ),
        json_schema_extra={"label": "pk 不稳定范围", "hint": "取值 [0, ∞)，如 1 表示 50cm 可挑战 100cm 以内"},
    )
    pk_unstable_range_v2_edge: list[float] = Field(
        default_factory=lambda: [0.1, 0.9],
        description=(
            "取值范围 [0, 1]，pk没有绝对实力差距时胜率的边缘情况，不能低于 10%，不能高于 90%。"
            "格式为 [最小边缘, 最大边缘]"
        ),
        json_schema_extra={"label": "pk 胜率边缘", "hint": "[最小胜率, 最大胜率]，不能低于 0.1、高于 0.9"},
    )
    pk_plus_min: float = Field(
        default=0.5,
        description="pk胜利后增加长度的范围最小值",
        json_schema_extra={"label": "pk胜利增益最小值", "hint": "pk胜利后增长的下限（cm）"},
    )
    pk_plus_max: float = Field(
        default=1.5,
        description="pk胜利后增加长度的范围最大值",
        json_schema_extra={"label": "pk胜利增益最大值", "hint": "pk胜利后增长的上限（cm）"},
    )
    pk_negative_min: float = Field(
        default=0.3,
        description="pk失败者减少长度的范围最小值",
        json_schema_extra={"label": "pk失败惩罚最小值", "hint": "pk失败时缩短的下限（cm）"},
    )
    pk_negative_max: float = Field(
        default=1,
        description="pk失败者减少长度的范围最大值",
        json_schema_extra={"label": "pk失败惩罚最大值", "hint": "pk失败时缩短的上限（cm）"},
    )
    pk_guard_chinchin_length: float = Field(
        default=5,
        description="禁止对弱者一直pk刷长度，低于该长度的人会开启pk保护",
        json_schema_extra={"label": "pk保护长度", "hint": "低于该长度的人开启 pk 保护"},
    )
    ranking_list_length: int = Field(
        default=8,
        description="排行榜展示多少人",
        json_schema_extra={"label": "排行榜人数", "hint": "牛子排名展示的人数"},
    )


class RebirthLevelConfig(PluginConfigBase):
    """转生等级配置（level 为唯一 id，改动会破坏数据库）。"""

    __ui_label__ = "转生等级"
    __ui_icon__ = "arrow-up-circle"
    __ui_order__ = 0

    level: int = Field(
        default=1,
        description="转生等级，不要改已有level的值，这是唯一id，改了会破坏数据库",
        json_schema_extra={"label": "转生等级", "hint": "唯一 id，不要修改已有等级的值"},
    )
    name: str = Field(
        default="1转牛豪",
        description="转生等级显示的文本",
        json_schema_extra={"label": "等级名称", "hint": "转生等级显示的文本"},
    )
    cost_length: int = Field(
        default=200,
        description="本次转生需要的长度，1转要200，2转要500（花费200+300），以此类推",
        json_schema_extra={"label": "转生消耗", "hint": "本次转生需要的长度"},
    )
    weight: float = Field(
        default=1.5,
        description="转生后的打胶、pk等操作的加权系数",
        json_schema_extra={"label": "加权系数", "hint": "转生后打胶、pk 等操作的加权系数"},
    )
    fail_prob: float = Field(
        default=0.2,
        description="转生失败的概率 [0, 1]",
        json_schema_extra={"label": "失败概率", "hint": "转生失败的概率，取值 [0, 1]"},
    )
    fail_negative_min: int = Field(
        default=10,
        description="转生失败的惩罚范围最小值",
        json_schema_extra={"label": "失败惩罚最小值", "hint": "转生失败缩短长度的下限（cm）"},
    )
    fail_negative_max: int = Field(
        default=30,
        description="转生失败的惩罚范围最大值",
        json_schema_extra={"label": "失败惩罚最大值", "hint": "转生失败缩短长度的上限（cm）"},
    )


class RebirthConfig(PluginConfigBase):
    """转生配置。"""

    __ui_label__ = "转生"
    __ui_icon__ = "refresh-cw"
    __ui_order__ = 5

    levels: list[RebirthLevelConfig] = Field(
        default_factory=lambda: [
            RebirthLevelConfig(level=1, name="1转牛豪", cost_length=200, weight=1.5, fail_prob=0.2, fail_negative_min=10, fail_negative_max=30),
            RebirthLevelConfig(level=2, name="2转牛皇", cost_length=300, weight=2, fail_prob=0.4, fail_negative_min=20, fail_negative_max=60),
            RebirthLevelConfig(level=3, name="3转牛尊", cost_length=400, weight=2.5, fail_prob=0.6, fail_negative_min=40, fail_negative_max=120),
            RebirthLevelConfig(level=4, name="4转牛圣", cost_length=500, weight=3, fail_prob=0.8, fail_negative_min=80, fail_negative_max=240),
            RebirthLevelConfig(level=5, name="5转牛仙", cost_length=600, weight=3.5, fail_prob=0.99, fail_negative_min=160, fail_negative_max=480),
        ],
        description="转生等级列表，按 level 升序排列",
        json_schema_extra={"label": "转生等级列表", "hint": "5 个转生等级，level 为唯一 id"},
    )


class BadgeCategoryConfig(PluginConfigBase):
    """成就配置（id 为唯一 id，改动会破坏数据库）。

    ``conditions`` / ``additions`` 为字符串列表（WebUI 表单只支持一层对象数组、
    数组元素仅限标量，故用编码字符串承载 字段->表达式 映射，由 ``flatten_config``
    解析回原版 dict 结构）：

    - 条件编码：``"字段名|表达式"``，如 ``"pk_win_count|>=50"``；
    - 加成编码：``"字段名|表达式1,表达式2"``，如 ``"pk_weight|10%,1"``
      （``%`` 结尾为比例，纯数字为固定值，多条同时生效）。
    """

    __ui_label__ = "成就"
    __ui_icon__ = "award"
    __ui_order__ = 0

    id: int = Field(
        default=1,
        description="成就id，不要改已有id的值，这是唯一id，改了会破坏数据库",
        json_schema_extra={"label": "成就ID", "hint": "唯一 id，不要修改已有成就的值"},
    )
    name: str = Field(
        default="牛子掠夺者",
        description="成就名称",
        json_schema_extra={"label": "成就名称", "hint": "成就名称"},
    )
    description: str = Field(
        default="它说，可以上了",
        description="成就描述",
        json_schema_extra={"label": "成就描述", "hint": "成就描述"},
    )
    priority: int = Field(
        default=100,
        description="成就优先级，数字越大，展示时越靠前",
        json_schema_extra={"label": "优先级", "hint": "数字越大，展示时越靠前"},
    )
    conditions: list[str] = Field(
        default_factory=lambda: ["pk_win_count|>=50", "pk_plus_length_total|>=50"],
        description=(
            "成就达成条件，全部满足才达成。编码为 字段名|表达式，只支持 > 和 >= 两种运算符，"
            "如 pk_win_count|>=50。可用字段：glue_me_count、glue_target_count、glue_plus_count、"
            "glue_plus_length_total、glue_punish_count、glue_punish_length_total、pk_win_count、"
            "pk_lose_count、pk_plus_length_total、pk_punish_length_total、lock_me_count、"
            "lock_target_count、lock_plus_count、lock_punish_count、lock_plus_length_total、"
            "lock_punish_length_total"
        ),
        json_schema_extra={"label": "达成条件", "hint": "逐条填入：字段名|表达式，如 pk_win_count|>=50"},
    )
    additions: list[str] = Field(
        default_factory=lambda: ["pk_weight|10%,1"],
        description=(
            "成就加成，成就可以仅仅是名义上的，没有加成效果。编码为 字段名|表达式1,表达式2，"
            "% 结尾的是加成比例（如 10%），纯数字是固定值（如 1）。可用字段：pk_weight、lock_weight、glue_weight"
        ),
        json_schema_extra={"label": "成就加成", "hint": "逐条填入：字段名|表达式，如 pk_weight|10%,1"},
    )


class BadgeConfig(PluginConfigBase):
    """成就配置。"""

    __ui_label__ = "成就"
    __ui_icon__ = "award"
    __ui_order__ = 6

    categories: list[BadgeCategoryConfig] = Field(
        default_factory=lambda: [
            BadgeCategoryConfig(
                id=1,
                name="牛子掠夺者",
                description="它说，可以上了",
                priority=100,
                conditions=["pk_win_count|>=50", "pk_plus_length_total|>=50"],
                additions=["pk_weight|10%,1"],
            ),
            BadgeCategoryConfig(
                id=2,
                name="打胶大师",
                description="精湛的打胶要有仪式感",
                priority=90,
                conditions=["glue_plus_count|>=50", "glue_plus_length_total|>=100"],
                additions=["glue_weight|10%,1"],
            ),
        ],
        description="成就列表，id 为唯一 id",
        json_schema_extra={"label": "成就列表", "hint": "成就列表，id 为唯一 id"},
    )


class FarmCostStageConfig(PluginConfigBase):
    """修炼阶段配置。"""

    __ui_label__ = "修炼阶段"
    __ui_icon__ = "list-ordered"
    __ui_order__ = 1

    time: str = Field(
        default="1h",
        description="阶段时间，格式 AhBm，代表 A 小时 B 分钟，如 1h20m，可以省略部分，如 2h、30m",
        json_schema_extra={"label": "阶段时间", "hint": "格式 AhBm，如 1h、2h"},
    )
    status: str = Field(
        default="嗦气期",
        description="阶段名称，如 1h 以内是嗦气期，4h - 5h 是渡劫期，最后一个档位代表修炼结束",
        json_schema_extra={"label": "阶段名称", "hint": "修炼到该时间阶段的名称"},
    )


class FarmConfig(PluginConfigBase):
    """牛子仙境配置。"""

    __ui_label__ = "牛子仙境"
    __ui_icon__ = "sprout"
    __ui_order__ = 7

    start: str = Field(
        default="20:00",
        description="仙境开始的时间，24 小时制，格式 hh:mm，如 12:00",
        json_schema_extra={"label": "开放开始时间", "hint": "24 小时制，格式 hh:mm，如 20:00"},
    )
    duration: str = Field(
        default="10h",
        description="仙境开放持续的时间，格式 AhBm，代表 A 小时 B 分钟，如 1h20m，可以省略部分，如 2h、30m",
        json_schema_extra={"label": "开放持续时长", "hint": "格式 AhBm，如 10h、1h20m、30m"},
    )
    cost: list[FarmCostStageConfig] = Field(
        default_factory=lambda: [
            FarmCostStageConfig(time="1h", status="嗦气期"),
            FarmCostStageConfig(time="2h", status="筑胶期"),
            FarmCostStageConfig(time="3h", status="大乘期"),
            FarmCostStageConfig(time="4h", status="飞升期"),
            FarmCostStageConfig(time="5h", status="渡劫期"),
        ],
        description=(
            "修炼到各个时间阶段的名称，如 1h 以内是嗦气期，4h - 5h 是渡劫期，"
            "最后一个档位是 5h，代表 5h 修炼结束"
        ),
        json_schema_extra={"label": "修炼阶段", "hint": "按时间升序，最后一个档位代表修炼结束"},
    )
    reward_min: float = Field(
        default=0.01,
        description="牛子长度收益的最小百分比，如 0.02 代表 2% 最小长度收益",
        json_schema_extra={"label": "最小收益比例", "hint": "如 0.02 代表 2% 最小长度收益"},
    )
    reward_max: float = Field(
        default=0.07,
        description="牛子长度收益的最大百分比，如 0.07 代表 7% 最大长度收益",
        json_schema_extra={"label": "最大收益比例", "hint": "如 0.07 代表 7% 最大长度收益"},
    )
    reward_base: float = Field(
        default=5,
        description="牛子长度收益的基础值(单位cm)，因为长度太短没什么百分比收益，所以最终结果是 base + 百分比值",
        json_schema_extra={"label": "基础收益", "hint": "最终收益 = base + 百分比值（cm）"},
    )


class FriendsConfig(PluginConfigBase):
    """牛友配置。"""

    __ui_label__ = "牛友"
    __ui_icon__ = "users"
    __ui_order__ = 8

    max: int = Field(
        default=8,
        description="每个人最多拥有的朋友数量",
        json_schema_extra={"label": "好友上限", "hint": "每个人最多拥有的朋友数量"},
    )
    fee_friends: float = Field(
        default=0.2,
        description="朋友费的手续费，设定 0.3 系统会扣除 30%，剩下的转移",
        json_schema_extra={"label": "朋友费手续费", "hint": "设定 0.3 系统会扣除 30%，剩下的转移"},
    )
    cost_base: float = Field(
        default=0.01,
        description="基础朋友费百分比，0.01 代表每天收长度的 1% 作为朋友费",
        json_schema_extra={"label": "基础朋友费", "hint": "0.01 代表每天收长度的 1% 作为朋友费"},
    )
    cost_share: float = Field(
        default=0.001,
        description=(
            "被共享越多的人，他提供的加成越多，所以手续费要额外收 被享有人数 x share 的每日费用，"
            "如被 10 个人共享，每天他的朋友费会多 10 x 0.001 = 1%"
        ),
        json_schema_extra={"label": "共享附加费", "hint": "额外收取 被享有人数 x share 的每日费用"},
    )
    addition_pk_plus_base: float = Field(
        default=0.02,
        description="pk时，牛友会为你提供他长度 2% 的长度加成，更好的获胜",
        json_schema_extra={"label": "pk 加成·基础", "hint": "牛友提供其长度 2% 的长度加成"},
    )
    addition_pk_plus_share: float = Field(
        default=0.001,
        description="每被共享一次，提供的 pk 长度加成再多 0.1%，如被 10 人享有，加成再多 1%",
        json_schema_extra={"label": "pk 加成·共享", "hint": "每被共享一次，pk 加成再多 0.1%"},
    )
    addition_lock_plus_base: float = Field(
        default=0.1,
        description=(
            "你的牛友给你🔒时，长度加成会额外多 10%，注意好友关系是单向的，"
            "除非他的牛友里有你，否则你给他🔒没有加成"
        ),
        json_schema_extra={"label": "🔒 加成·基础", "hint": "牛友给你🔒时，长度加成额外多 10%"},
    )
    addition_lock_plus_share: float = Field(
        default=0.01,
        description="每被共享一次，再多加成 1%",
        json_schema_extra={"label": "🔒 加成·共享", "hint": "每被共享一次，再多加成 1%"},
    )
    addition_glue_plus_base: float = Field(
        default=0.1,
        description="你的牛友给你打胶时，长度加成会额外多 10%",
        json_schema_extra={"label": "打胶加成·基础", "hint": "牛友给你打胶时，长度加成额外多 10%"},
    )
    addition_glue_plus_share: float = Field(
        default=0.01,
        description="每被共享一次，再多加成 1%",
        json_schema_extra={"label": "打胶加成·共享", "hint": "每被共享一次，再多加成 1%"},
    )


class DickyPKConfig(PluginConfigBase):
    """牛子PK 插件配置（全量强类型，默认值与原版 config.json 逐一相等）。"""

    __ui_label__ = "牛子PK"
    __ui_icon__ = "gamepad-2"
    __ui_order__ = 0

    plugin: PluginSectionConfig = Field(
        default_factory=PluginSectionConfig,
        description="插件基础配置",
        json_schema_extra={"label": "插件", "hint": "插件开关与配置版本"},
    )
    basic: BasicConfig = Field(
        default_factory=BasicConfig,
        description="基础配置：注册长度、每日上限与 CD 触发",
        json_schema_extra={"label": "基础", "hint": "注册长度、每日上限与 CD 触发"},
    )
    lock: LockConfig = Field(
        default_factory=LockConfig,
        description="🔒 相关配置",
        json_schema_extra={"label": "🔒 锁", "hint": "🔒 自己与🔒 别人的奖惩参数"},
    )
    glue: GlueConfig = Field(
        default_factory=GlueConfig,
        description="打胶相关配置",
        json_schema_extra={"label": "打胶", "hint": "打胶自己与打胶别人的奖惩参数"},
    )
    pk: PKConfig = Field(
        default_factory=PKConfig,
        description="pk 相关配置",
        json_schema_extra={"label": "PK", "hint": "pk 胜负判定与奖惩参数"},
    )
    rebirth: RebirthConfig = Field(
        default_factory=RebirthConfig,
        description="转生配置",
        json_schema_extra={"label": "转生", "hint": "转生等级列表"},
    )
    badge: BadgeConfig = Field(
        default_factory=BadgeConfig,
        description="成就配置",
        json_schema_extra={"label": "成就", "hint": "成就列表"},
    )
    farm: FarmConfig = Field(
        default_factory=FarmConfig,
        description="牛子仙境配置",
        json_schema_extra={"label": "牛子仙境", "hint": "仙境开放时间、修炼阶段与收益"},
    )
    friends: FriendsConfig = Field(
        default_factory=FriendsConfig,
        description="牛友配置",
        json_schema_extra={"label": "牛友", "hint": "好友上限、朋友费与加成"},
    )
