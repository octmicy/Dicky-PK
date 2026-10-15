"""配置扁平桥。

把 ``dicky_pk.config.DickyPKConfig`` 强类型模型拍扁成原版 ``src/config.json`` 的键形，
供全部游戏逻辑（db/main/badge/farm/friends/rebirth/cd）以 ``Config.get_config(key)`` 读取。

设计约束：
- 模块导入无副作用：不读盘、不建目录、不建连接（原版的磁盘读写与模板落盘全部删除）；
- 数据来源由 ``plugin.py`` 在 ``on_load`` / ``on_config_update`` 时经 ``init(flat)`` 注入；
- ``is_pk_win`` 公式与原版逐字一致；
- ``deprecated_tips`` / ``modify_config_in_runtime`` 随原版废弃逻辑一并删除。
"""

from __future__ import annotations

from ..config import DickyPKConfig
from .config_parser import TimeParser
from .utils import Random, fixed_two_decimal_digits

# 扁平桥中平铺到顶层的配置节（字段名与原 config.json 键名完全一致）
_FLAT_SECTIONS = ("basic", "lock", "glue", "pk")
# 扁平桥中保持嵌套的配置节
_NESTED_SECTIONS = ("rebirth", "badge", "farm", "friends")


def _restore_number(text: str):
    """把纯数字字符串还原为 int/float（原 config.json 的 addition 里混有数字）。"""
    try:
        number = float(text)
    except ValueError:
        return text
    return int(number) if number.is_integer() else number


def flatten_config(model: DickyPKConfig) -> dict:
    """把强类型配置模型拍扁成原 ``config.json`` 的键形。

    映射规则：
    - ``basic`` / ``lock`` / ``glue`` / ``pk`` 四节的字段平铺到顶层（键名不变）；
    - ``rebirth`` / ``badge`` / ``farm`` / ``friends`` 四节保持嵌套字典；
    - WebUI 表单只支持一层对象数组且元素仅限标量，因此模型里 ``badge`` 的条件/加成是
      编码字符串列表（``字段名|表达式``）、``farm`` 的开始/时长/收益与 ``friends`` 的
      费用/加成是拍平标量——这里还原成原 ``config.json`` 的嵌套 dict 键形，游戏逻辑无感知；
    - ``plugin`` 节为宿主保留节，不出现在扁平结果中。

    Args:
        model: ``DickyPKConfig`` 强类型配置实例。

    Returns:
        dict: 原 ``config.json`` 键形的配置字典。
    """

    data = model.model_dump(mode="python")
    flat: dict = {}
    for section in _FLAT_SECTIONS:
        values = data.pop(section, None)
        if isinstance(values, dict):
            flat.update(values)
    for section in _NESTED_SECTIONS:
        if section in data:
            flat[section] = data[section]

    # badge：conditions/additions 编码字符串列表 → condition/addition 字典
    #   条件编码 "字段名|表达式"（如 pk_win_count|>=50）
    #   加成编码 "字段名|表达式1,表达式2"（如 pk_weight|10%,1）
    badge = flat.get("badge")
    if isinstance(badge, dict):
        for category in badge.get("categories", []):
            condition: dict = {}
            for token in category.pop("conditions", []):
                field, _, expr = str(token).partition("|")
                condition[field.strip()] = expr.strip()
            category["condition"] = condition
            addition: dict = {}
            for token in category.pop("additions", []):
                field, _, exprs = str(token).partition("|")
                addition[field.strip()] = [
                    _restore_number(expr) for expr in exprs.split(",") if expr.strip()
                ]
            category["addition"] = addition

    # farm：拍平的开始/时长/收益 → can_play_time/reward 嵌套字典
    farm = flat.get("farm")
    if isinstance(farm, dict):
        farm["can_play_time"] = {
            "start": farm.pop("start"),
            "duration": farm.pop("duration"),
        }
        farm["reward"] = {
            "min": farm.pop("reward_min"),
            "max": farm.pop("reward_max"),
            "base": farm.pop("reward_base"),
        }

    # friends：拍平的费用/加成 → fee/cost/addition 嵌套字典
    friends = flat.get("friends")
    if isinstance(friends, dict):
        friends["fee"] = {"friends": friends.pop("fee_friends")}
        friends["cost"] = {
            "base": friends.pop("cost_base"),
            "share": friends.pop("cost_share"),
        }
        friends["addition"] = {
            "pk_plus": {
                "base": friends.pop("addition_pk_plus_base"),
                "share": friends.pop("addition_pk_plus_share"),
            },
            "lock_plus": {
                "base": friends.pop("addition_lock_plus_base"),
                "share": friends.pop("addition_lock_plus_share"),
            },
            "glue_plus": {
                "base": friends.pop("addition_glue_plus_base"),
                "share": friends.pop("addition_glue_plus_share"),
            },
        }
    return flat


class Config:
    """游戏逻辑配置入口（静态方法签名与原版 ``src/config.py`` 保持一致）。"""

    sub_parser_time = TimeParser()

    _flat: dict = {}

    @classmethod
    def init(cls, flat: dict) -> None:
        """注入扁平配置字典（由 plugin.py 在 on_load / on_config_update 时调用）。"""
        cls._flat = dict(flat or {})

    @classmethod
    def read_config(cls) -> dict:
        """返回当前扁平配置字典（原 read_config 的内存替身，不再读盘）。"""
        return cls._flat

    @classmethod
    def get_config(cls, key: str):
        return cls.read_config().get(key)

    @classmethod
    def new_chinchin_length(cls):
        min = cls.get_config("new_chinchin_length_random_min")
        max = cls.get_config("new_chinchin_length_random_max")
        return cls.random_value(min, max)

    @staticmethod
    def random_value(min: float, max: float):
        return fixed_two_decimal_digits(
            min + (max - min) * Random.random(), to_number=True
        )

    @staticmethod
    def is_hit_with_rate(rate: float):
        return Random.random() < rate

    @classmethod
    def is_hit(cls, key: str):
        rate = cls.get_config(key)
        return cls.is_hit_with_rate(rate)

    @classmethod
    def get_lock_me_punish_value(cls):
        min = cls.get_config("lock_me_negative_min")
        max = cls.get_config("lock_me_negative_max")
        return cls.random_value(min, max)

    @classmethod
    def get_lock_plus_value(cls):
        min = cls.get_config("lock_plus_min")
        max = cls.get_config("lock_plus_max")
        return cls.random_value(min, max)

    @classmethod
    def get_glue_plus_value(cls):
        min = cls.get_config("glue_plus_min")
        max = cls.get_config("glue_plus_max")
        return cls.random_value(min, max)

    @classmethod
    def is_pk_win(cls, user_length: float, target_length: float):
        """
        TODO: 限制一下强者挑战弱者，900cm 挑战 100cm 存在输的可能性，但是 100cm 挑战 900cm 必输。
        """
        range = cls.get_config("pk_unstable_range_v2")
        edge = cls.get_config("pk_unstable_range_v2_edge")
        min_edge = edge[0]
        max_edge = edge[1]
        offset = user_length * range
        min_can_pk_length = user_length - offset
        max_can_pk_length = user_length + offset
        is_in_range = (min_can_pk_length <= target_length) and (
            target_length <= max_can_pk_length
        )
        if not is_in_range:
            # 绝对赢
            if user_length > target_length:
                return True
            # 绝对输
            else:
                return False
        # 随机胜负计算
        if user_length > target_length:
            #         t   u
            # |---l---|-w-|
            # |-----------|-----------|
            win_rate = (user_length - target_length) / offset
        else:
            #             u   t
            #             |-l-|---w---|
            # |-----------|-----------|
            win_rate = (max_can_pk_length - target_length) / offset
        # edge check
        if win_rate < min_edge:
            win_rate = min_edge
        elif win_rate > max_edge:
            win_rate = max_edge
        return cls.is_hit_with_rate(win_rate)

    @classmethod
    def get_pk_plus_value(cls):
        min = cls.get_config("pk_plus_min")
        max = cls.get_config("pk_plus_max")
        return cls.random_value(min, max)

    @classmethod
    def get_pk_punish_value(cls):
        min = cls.get_config("pk_negative_min")
        max = cls.get_config("pk_negative_max")
        return cls.random_value(min, max)

    @classmethod
    def get_glue_punish_value(cls):
        min = cls.get_config("glue_negative_min")
        max = cls.get_config("glue_negative_max")
        return cls.random_value(min, max)

    @classmethod
    def get_lock_punish_with_strong_person_value(cls):
        min = cls.get_config("lock_me_negative_with_strong_person_min")
        max = cls.get_config("lock_me_negative_with_strong_person_max")
        return cls.random_value(min, max)

    @classmethod
    def get_glue_self_punish_value(cls):
        min = cls.get_config("glue_self_negative_min")
        max = cls.get_config("glue_self_negative_max")
        return cls.random_value(min, max)
