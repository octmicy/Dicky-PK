"""SQLite 存储层。

从原版 ``nonebot_plugin_dicky_pk/src/db.py`` 移植，六张表 DDL 与原版逐字一致。

相对原版的变化（详见 ``docs/porting-contract.md`` §3）：
- 删除 ``Paths`` / ``MigrationHelper`` 与旧版 ``data/`` 路径逻辑；SQLite 文件固定为
  ``<ctx.paths.data_dir>/data.sqlite``，不迁移任何旧数据（决策③）；
- 用户身份键由整数 qq 改为 ``platform:user_id`` 复合键字符串（决策①）：所有把键嵌入
  SQL 的位置统一经 ``_k()`` 引号化（格式校验 + 单引号转义），insert/update 中本就传入
  参字典的位置改用 ``:qq`` 命名参数绑定；
- 模块导入无副作用（铁律②）：不连库、不建目录、不读文件，初始化只发生在
  ``init_database`` / ``lazy_init_database``；
- ``lazy_init_database`` 不再调用已删除的 ``Config.deprecated_tips``；
- 形参类型注解 ``qq: int`` → ``qq: str``（仅注解，无运行时影响）。
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .config import Config
from .constants import FarmConst, TimeConst
from .rebirth_view import RebirthSystem_View
from .utils import ArrowUtil, NumberUtils, fixed_two_decimal_digits

sql_ins = None

# SQLite 文件名（位于 ctx.paths.data_dir 下）
SQLITE_FILE_NAME = "data.sqlite"

# 用户身份复合键格式："platform:user_id"（如 "qq:12345"）。
# 允许除单引号与逗号外的任意字符（含空格、@、中文等）：单引号会破坏 SQL 字符串
# 字面量（语法错误/注入），逗号会破坏 friends_list 的逗号分隔存储
# （friends.py:33-36/113-118，移植契约 §3.3）。其余字符经 _k() 的单引号包裹 +
# 转义后嵌入 SQL 是安全的。
_USER_KEY_RE = re.compile(r"[^',]+")

# init_database 记住的数据目录，供 lazy_init_database（close 之后）重连使用
_data_dir: Path | None = None


def _k(qq) -> str:
    """把用户身份复合键安全地嵌入 SQL 字面量。

    复合键是字符串，裸插会得到 SQL 语法错误（且可被注入），这里统一做：
    格式校验（禁单引号/逗号，见 _USER_KEY_RE）+ 单引号包裹 + 单引号转义，
    杜绝注入与语法错误。仅当 platform/user_id 自身含单引号或逗号时抛
    ValueError——那会破坏 SQL 字面量与 friends_list 逗号存储，必须失败关闭。
    """
    key = str(qq)
    if not _USER_KEY_RE.fullmatch(key):
        raise ValueError(f"dicky_pk: 非法的用户身份键: {key!r}")
    return "'" + key.replace("'", "''") + "'"


class Sql_UserInfo:
    @staticmethod
    def _empty_data_handler(data: dict):
        if data["latest_speech_nickname"] is None:
            data["latest_speech_nickname"] = ""
        return data

    @staticmethod
    def _sql_create_table():
        return "create table if not exists `info` (`qq` bigint, `latest_speech_nickname` varchar(255), `latest_speech_group` bigint, primary key (`qq`));"

    @classmethod
    def _sql_insert_single_data(cls, data: dict):
        data = cls._empty_data_handler(data)
        return 'insert into `info` (`latest_speech_group`, `latest_speech_nickname`, `qq`) values (:latest_speech_group, :latest_speech_nickname, :qq);'

    @staticmethod
    def _sql_select_single_data(qq: str):
        return f"select * from `info` where `qq` = {_k(qq)};"

    @staticmethod
    def _sql_check_table_exists():
        return (
            'select count(*) from sqlite_master where type = "table" and name = "info";'
        )

    @classmethod
    def _sql_update_single_data(cls, data: dict):
        data = cls._empty_data_handler(data)
        return 'update `info` set `latest_speech_nickname` = :latest_speech_nickname, `latest_speech_group` = :latest_speech_group where `qq` = :qq;'

    @staticmethod
    def _sql_batch_select_data(qqs: list):
        return f"select * from `info` where `qq` in {Sql.utils.tupleify(qqs)};"

    @staticmethod
    def _sql_delete_single_data(qq: str):
        return f"delete from `info` where `qq` = {_k(qq)};"

    @staticmethod
    def deserialize(data: tuple):
        return {
            "qq": data[0],
            "latest_speech_nickname": data[1],
            "latest_speech_group": data[2],
        }

    @classmethod
    def select_single_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_select_single_data(qq))
        one = sql_ins.cursor.fetchone()
        if one is None:
            return None
        return cls.deserialize(one)

    @classmethod
    def select_batch_data_by_qqs(cls, qqs: list):
        sql_ins.cursor.execute(cls._sql_batch_select_data(qqs))
        return [cls.deserialize(data) for data in sql_ins.cursor.fetchall()]

    @classmethod
    def delete_single_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_delete_single_data(qq))
        sql_ins.conn.commit()


class Sql_rebirth:
    @staticmethod
    def _sql_create_table():
        return "create table if not exists `rebirth` (`qq` bigint, `latest_rebirth_time` varchar(255), `level` integer, primary key (`qq`));"

    @staticmethod
    def _sql_insert_single_data(data: dict):
        return 'insert into `rebirth` (`level`, `latest_rebirth_time`, `qq`) values (:level, :latest_rebirth_time, :qq);'

    @staticmethod
    def _sql_select_single_data(qq: str):
        return f"select * from `rebirth` where `qq` = {_k(qq)};"

    @staticmethod
    def _sql_batch_select_data(qqs: list):
        return f"select * from `rebirth` where `qq` in {Sql.utils.tupleify(qqs)};"

    @staticmethod
    def _sql_check_table_exists():
        return 'select count(*) from sqlite_master where type = "table" and name = "rebirth";'

    @staticmethod
    def _sql_update_single_data(data: dict):
        return 'update `rebirth` set `level` = :level, `latest_rebirth_time` = :latest_rebirth_time where `qq` = :qq;'

    @staticmethod
    def _sql_delete_single_data(qq: str):
        return f"delete from `rebirth` where `qq` = {_k(qq)};"

    @staticmethod
    def deserialize(data: tuple):
        return {
            "qq": data[0],
            "latest_rebirth_time": data[1],
            "level": data[2],
        }

    @classmethod
    def select_single_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_select_single_data(qq))
        one = sql_ins.cursor.fetchone()
        if one is None:
            return None
        return cls.deserialize(one)

    @classmethod
    def insert_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls._sql_insert_single_data(data), data)
        sql_ins.conn.commit()

    @classmethod
    def update_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls._sql_update_single_data(data), data)
        sql_ins.conn.commit()

    @classmethod
    def delete_single_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_delete_single_data(qq))
        sql_ins.conn.commit()

    @classmethod
    def select_batch_data_by_qqs(cls, qqs: list):
        sql_ins.cursor.execute(cls._sql_batch_select_data(qqs))
        return [cls.deserialize(data) for data in sql_ins.cursor.fetchall()]


class DB_Rebirth:
    @staticmethod
    def get_rebirth_data(qq: str):
        return Sql_rebirth.select_single_data(qq)

    @staticmethod
    def insert_rebirth_data(data: dict):
        Sql_rebirth.insert_single_data(data)

    @staticmethod
    def update_rebirth_data(data: dict):
        Sql_rebirth.update_single_data(data)


class Sql_badge:
    @staticmethod
    def _sql_create_table():
        return "create table if not exists `badge` (`qq` bigint, `badge_ids` varchar(255), `glue_me_count` bigint, `glue_target_count` bigint, `glue_plus_count` bigint, `glue_plus_length_total` bigint, `glue_punish_count` bigint, `glue_punish_length_total` bigint, `pk_win_count` bigint, `pk_lose_count` bigint, `pk_plus_length_total` bigint, `pk_punish_length_total` bigint, `lock_me_count` bigint, `lock_target_count` bigint, `lock_plus_count` bigint, `lock_punish_count` bigint, `lock_plus_length_total` bigint, `lock_punish_length_total` bigint, primary key (`qq`));"

    @staticmethod
    def _sql_insert_single_data(data: dict):
        return 'insert into `badge` (`qq`, `badge_ids`, `glue_me_count`, `glue_target_count`, `glue_plus_count`, `glue_plus_length_total`, `glue_punish_count`, `glue_punish_length_total`, `pk_win_count`, `pk_lose_count`, `pk_plus_length_total`, `pk_punish_length_total`, `lock_me_count`, `lock_target_count`, `lock_plus_count`, `lock_punish_count`, `lock_plus_length_total`, `lock_punish_length_total`) values (:qq, :badge_ids, :glue_me_count, :glue_target_count, :glue_plus_count, :glue_plus_length_total, :glue_punish_count, :glue_punish_length_total, :pk_win_count, :pk_lose_count, :pk_plus_length_total, :pk_punish_length_total, :lock_me_count, :lock_target_count, :lock_plus_count, :lock_punish_count, :lock_plus_length_total, :lock_punish_length_total);'

    @staticmethod
    def _sql_select_single_data(qq: str):
        return f"select * from `badge` where `qq` = {_k(qq)};"

    @staticmethod
    def _sql_batch_select_data(qqs: list):
        return f"select * from `badge` where `qq` in {Sql.utils.tupleify(qqs)};"

    @staticmethod
    def _sql_update_single_data(data: dict):
        return 'update `badge` set `badge_ids` = :badge_ids, `glue_me_count` = :glue_me_count, `glue_target_count` = :glue_target_count, `glue_plus_count` = :glue_plus_count, `glue_plus_length_total` = :glue_plus_length_total, `glue_punish_count` = :glue_punish_count, `glue_punish_length_total` = :glue_punish_length_total, `pk_win_count` = :pk_win_count, `pk_lose_count` = :pk_lose_count, `pk_plus_length_total` = :pk_plus_length_total, `pk_punish_length_total` = :pk_punish_length_total, `lock_me_count` = :lock_me_count, `lock_target_count` = :lock_target_count, `lock_plus_count` = :lock_plus_count, `lock_punish_count` = :lock_punish_count, `lock_plus_length_total` = :lock_plus_length_total, `lock_punish_length_total` = :lock_punish_length_total where `qq` = :qq;'

    @staticmethod
    def _sql_delete_single_data(qq: str):
        return f"delete from `badge` where `qq` = {_k(qq)};"

    @staticmethod
    def _sql_check_table_exist():
        return 'select count(*) from sqlite_master where type = "table" and name = "badge";'

    @staticmethod
    def deserialize(data: tuple):
        return {
            "qq": data[0],
            "badge_ids": data[1],
            "glue_me_count": data[2],
            "glue_target_count": data[3],
            "glue_plus_count": data[4],
            "glue_plus_length_total": data[5],
            "glue_punish_count": data[6],
            "glue_punish_length_total": data[7],
            "pk_win_count": data[8],
            "pk_lose_count": data[9],
            "pk_plus_length_total": data[10],
            "pk_punish_length_total": data[11],
            "lock_me_count": data[12],
            "lock_target_count": data[13],
            "lock_plus_count": data[14],
            "lock_punish_count": data[15],
            "lock_plus_length_total": data[16],
            "lock_punish_length_total": data[17],
        }

    @classmethod
    def select_single_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_select_single_data(qq))
        one = sql_ins.cursor.fetchone()
        if one is None:
            return None
        return cls.deserialize(one)

    @classmethod
    def insert_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls._sql_insert_single_data(data), data)
        sql_ins.conn.commit()

    @classmethod
    def update_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls._sql_update_single_data(data), data)
        sql_ins.conn.commit()

    @classmethod
    def delete_single_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_delete_single_data(qq))
        sql_ins.conn.commit()

    @classmethod
    def select_batch_data_by_qqs(cls, qqs: list):
        sql_ins.cursor.execute(cls._sql_batch_select_data(qqs))
        return [cls.deserialize(data) for data in sql_ins.cursor.fetchall()]


class DB_Badge:
    @staticmethod
    def init_user_data(qq: str, at_qq: str = None):
        for account in [qq, at_qq]:
            if account is None:
                continue
            data = Sql_badge.select_single_data(account)
            if data is None:
                data = {
                    "qq": account,
                    "badge_ids": "",
                    "glue_me_count": 0,
                    "glue_target_count": 0,
                    "glue_plus_count": 0,
                    "glue_plus_length_total": 0,
                    "glue_punish_count": 0,
                    "glue_punish_length_total": 0,
                    "pk_win_count": 0,
                    "pk_lose_count": 0,
                    "pk_plus_length_total": 0,
                    "pk_punish_length_total": 0,
                    "lock_me_count": 0,
                    "lock_target_count": 0,
                    "lock_plus_count": 0,
                    "lock_punish_count": 0,
                    "lock_plus_length_total": 0,
                    "lock_punish_length_total": 0,
                }
                Sql_badge.insert_single_data(data)

    @classmethod
    def plus_value_by_ley(cls, qq: str, key: str, plus_value: int):
        data = Sql_badge.select_single_data(qq)
        if data is None:
            cls.init_user_data(qq)
            cls.plus_value_by_ley(qq, key, plus_value)
        else:
            new_value = data[key] + plus_value
            # if total data, fixed 2
            if key.endswith("total"):
                new_value = fixed_two_decimal_digits(new_value, to_number=True)
            data[key] = new_value
            Sql_badge.update_single_data(data)

    @classmethod
    def record_glue_me_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "glue_me_count", 1)

    @classmethod
    def record_glue_target_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "glue_target_count", 1)

    @classmethod
    def record_glue_plus_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "glue_plus_count", 1)

    @classmethod
    def record_glue_plus_length_total(cls, qq: str, length: float):
        cls.plus_value_by_ley(qq, "glue_plus_length_total", length)

    @classmethod
    def record_glue_punish_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "glue_punish_count", 1)

    @classmethod
    def record_glue_punish_length_total(cls, qq: str, length: float):
        cls.plus_value_by_ley(qq, "glue_punish_length_total", length)

    @classmethod
    def record_pk_win_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "pk_win_count", 1)

    @classmethod
    def record_pk_lose_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "pk_lose_count", 1)

    @classmethod
    def record_pk_plus_length_total(cls, qq: str, length: float):
        cls.plus_value_by_ley(qq, "pk_plus_length_total", length)

    @classmethod
    def record_pk_punish_length_total(cls, qq: str, length: float):
        cls.plus_value_by_ley(qq, "pk_punish_length_total", length)

    @classmethod
    def record_lock_me_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "lock_me_count", 1)

    @classmethod
    def record_lock_target_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "lock_target_count", 1)

    @classmethod
    def record_lock_plus_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "lock_plus_count", 1)

    @classmethod
    def record_lock_punish_count(cls, qq: str):
        cls.plus_value_by_ley(qq, "lock_punish_count", 1)

    @classmethod
    def record_lock_plus_length_total(cls, qq: str, length: float):
        cls.plus_value_by_ley(qq, "lock_plus_length_total", length)

    @classmethod
    def record_lock_punish_length_total(cls, qq: str, length: float):
        cls.plus_value_by_ley(qq, "lock_punish_length_total", length)

    @staticmethod
    def get_badge_data(qq: str):
        return Sql_badge.select_single_data(qq)

    @staticmethod
    def update_badge_ids(qq: str, badge_ids: list):
        data = Sql_badge.select_single_data(qq)
        data["badge_ids"] = badge_ids
        Sql_badge.update_single_data(data)


class Sql_farm:
    @staticmethod
    def _sql_create_table():
        return "create table if not exists `farm` (`qq` bigint, `farm_status` varchar(255), `farm_latest_plant_time` varchar(255), `farm_need_time` integer, `farm_count` integer, `farm_expect_get_length` float, primary key (`qq`));"

    @staticmethod
    def _sql_insert_single_data():
        return "insert into `farm` (`qq`, `farm_status`, `farm_latest_plant_time`, `farm_need_time`, `farm_count`, `farm_expect_get_length`) values (:qq, :farm_status, :farm_latest_plant_time, :farm_need_time, :farm_count, :farm_expect_get_length);"

    @staticmethod
    def _sql_select_single_data(qq: str):
        return f"select * from `farm` where `qq` = {_k(qq)};"

    @staticmethod
    def _sql_batch_select_data(qqs: list):
        return f"select * from `farm` where `qq` in {Sql.utils.tupleify(qqs)};"

    @staticmethod
    def _sql_update_single_data():
        return "update `farm` set `farm_status` = :farm_status, `farm_latest_plant_time` = :farm_latest_plant_time, `farm_need_time` = :farm_need_time, `farm_count` = :farm_count, `farm_expect_get_length` = :farm_expect_get_length where `qq` = :qq;"

    @staticmethod
    def _sql_delete_single_data(qq: str):
        return f"delete from `farm` where `qq` = {_k(qq)};"

    @staticmethod
    def _sql_check_table_exists():
        return 'select count(*) from sqlite_master where type="table" and name="farm";'

    @staticmethod
    def deserialize(data: tuple):
        return {
            "qq": data[0],
            "farm_status": data[1],
            "farm_latest_plant_time": data[2],
            "farm_need_time": data[3],
            "farm_count": data[4],
            "farm_expect_get_length": data[5],
        }

    @classmethod
    def select_signle_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_select_single_data(qq))
        one = sql_ins.cursor.fetchone()
        if one is None:
            return None
        return cls.deserialize(one)

    @classmethod
    def insert_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls._sql_insert_single_data(), data)
        sql_ins.conn.commit()

    @classmethod
    def update_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls._sql_update_single_data(), data)
        sql_ins.conn.commit()

    @classmethod
    def delete_single_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_delete_single_data(qq))
        sql_ins.conn.commit()

    @classmethod
    def select_batch_data_by_qqs(cls, qqs: list):
        sql_ins.cursor.execute(cls._sql_batch_select_data(qqs))
        return [cls.deserialize(data) for data in sql_ins.cursor.fetchall()]


class DB_Farm:
    @staticmethod
    def init_user_data(qq: str, at_qq: str = None):
        for account in [qq, at_qq]:
            if account is None:
                continue
            data = Sql_farm.select_signle_data(account)
            if data is None:
                Sql_farm.insert_single_data(
                    {
                        "qq": account,
                        "farm_status": FarmConst.status_empty,
                        "farm_latest_plant_time": TimeConst.DEFAULT_NONE_TIME,
                        "farm_need_time": 0,
                        "farm_count": 0,
                        "farm_expect_get_length": 0,
                    }
                )

    @staticmethod
    def get_user_data(qq: str):
        return Sql_farm.select_signle_data(qq)

    @staticmethod
    def update_user_data(data: dict):
        Sql_farm.update_single_data(data)


class Sql_friends:
    @staticmethod
    def _sql_create_table():
        return "create table if not exists `friends` (`qq` bigint, `friends_list` varchar(255), `friends_share_count` integer, `friends_cost_latest_time` varchar(255), `friends_will_collect_length` float, `friends_collect_latest_time` varchar(255), primary key (`qq`));"

    @staticmethod
    def _sql_insert_single_data():
        return "insert into `friends` (`qq`, `friends_list`, `friends_share_count`, `friends_cost_latest_time`, `friends_will_collect_length`, `friends_collect_latest_time`) values (:qq, :friends_list, :friends_share_count, :friends_cost_latest_time, :friends_will_collect_length, :friends_collect_latest_time);"

    @staticmethod
    def _sql_select_single_data(qq: str):
        return f"select * from `friends` where `qq` = {_k(qq)};"

    @staticmethod
    def _sql_batch_select_data(qqs: list):
        return f"select * from `friends` where `qq` in {Sql.utils.tupleify(qqs)};"

    @staticmethod
    def _sql_update_single_data():
        return "update `friends` set `friends_list` = :friends_list, `friends_share_count` = :friends_share_count, `friends_cost_latest_time` = :friends_cost_latest_time, `friends_will_collect_length` = :friends_will_collect_length, `friends_collect_latest_time` = :friends_collect_latest_time where `qq` = :qq;"

    @staticmethod
    def _sql_delete_single_data(qq: str):
        return f"delete from `friends` where `qq` = {_k(qq)};"

    @staticmethod
    def _sql_check_table_exists():
        return (
            'select count(*) from sqlite_master where type="table" and name="friends";'
        )

    @staticmethod
    def deserialize(data: tuple):
        return {
            "qq": data[0],
            "friends_list": data[1],
            "friends_share_count": data[2],
            "friends_cost_latest_time": data[3],
            "friends_will_collect_length": data[4],
            "friends_collect_latest_time": data[5],
        }

    @classmethod
    def select_signle_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_select_single_data(qq))
        one = sql_ins.cursor.fetchone()
        if one is None:
            return None
        return cls.deserialize(one)

    @classmethod
    def insert_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls._sql_insert_single_data(), data)
        sql_ins.conn.commit()

    @classmethod
    def update_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls._sql_update_single_data(), data)
        sql_ins.conn.commit()

    @classmethod
    def delete_single_data(cls, qq: str):
        sql_ins.cursor.execute(cls._sql_delete_single_data(qq))
        sql_ins.conn.commit()

    @classmethod
    def select_batch_data_by_qqs(cls, qqs: list):
        sql_ins.cursor.execute(cls._sql_batch_select_data(qqs))
        return [cls.deserialize(data) for data in sql_ins.cursor.fetchall()]


class DB_Friends:
    @staticmethod
    def init_user_data(qq: str, at_qq: str = None):
        for account in [qq, at_qq]:
            if account is None:
                continue
            data = Sql_friends.select_signle_data(account)
            if data is None:
                Sql_friends.insert_single_data(
                    {
                        "qq": account,
                        "friends_list": "",
                        "friends_share_count": 0,
                        "friends_cost_latest_time": TimeConst.DEFAULT_NONE_TIME,
                        "friends_will_collect_length": 0,
                        "friends_collect_latest_time": TimeConst.DEFAULT_NONE_TIME,
                    }
                )

    @staticmethod
    def get_user_data(qq: str):
        return Sql_friends.select_signle_data(qq)

    @staticmethod
    def update_user_data(data: dict):
        # FIXME: 兜底数据格式
        is_friends_list_typeof_arr = isinstance(data["friends_list"], list)
        if is_friends_list_typeof_arr:
            # stringify and join
            new_list = ",".join([str(q) for q in data["friends_list"]])
            data["friends_list"] = new_list
        Sql_friends.update_single_data(data)

    @staticmethod
    def get_batch_user_data(qqs: list):
        return Sql_friends.select_batch_data_by_qqs(qqs)

class Sql_utils():

    @staticmethod
    def tupleify(data: list):
        # 复合键是字符串：逐项引号化并转义（_k 内含格式校验）。
        # 空列表生成 "()"，与原版行为一致（SQLite 的 `in ()` 恒为空集，已实测）。
        return "(" + ", ".join(_k(item) for item in data) + ")"

class Sql:

    sub_table_info = Sql_UserInfo()
    sub_table_rebirth = Sql_rebirth()
    sub_table_badge = Sql_badge()
    sub_table_farm = Sql_farm()
    sub_table_friends = Sql_friends()

    utils = Sql_utils()

    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.conn = sqlite3.connect(self.sqlite_path)
        self.cursor = self.conn.cursor()

    @staticmethod
    def __sql_create_table():
        return "create table if not exists `users` (`qq` bigint, `length` float, `daily_lock_count` integer, `daily_pk_count` integer, `daily_glue_count` integer, `register_time` varchar(255), `latest_daily_lock` varchar(255), `latest_daily_pk` varchar(255), `latest_daily_glue` varchar(255), `pk_time` varchar(255), `pked_time` varchar(255), `glueing_time` varchar(255), `glued_time` varchar(255), `locked_time` varchar(255), primary key (`qq`));"

    @staticmethod
    def __sql_insert_single_data(data: dict):
        return f'insert into `users` (`daily_glue_count`, `daily_lock_count`, `daily_pk_count`, `glued_time`, `glueing_time`, `latest_daily_glue`, `latest_daily_lock`, `latest_daily_pk`, `length`, `locked_time`, `pk_time`, `pked_time`, `qq`, `register_time`) values ({data["daily_glue_count"]}, {data["daily_lock_count"]}, {data["daily_pk_count"]}, "{data["glued_time"]}", "{data["glueing_time"]}", "{data["latest_daily_glue"]}", "{data["latest_daily_lock"]}", "{data["latest_daily_pk"]}", {data["length"]}, "{data["locked_time"]}", "{data["pk_time"]}", "{data["pked_time"]}", {_k(data["qq"])}, "{data["register_time"]}");'

    @staticmethod
    def __sql_select_single_data(qq: str):
        return f"select * from `users` where `qq` = {_k(qq)};"

    @staticmethod
    def __sql_check_table_exists():
        return 'select count(*) from sqlite_master where type = "table" and name = "users";'

    @staticmethod
    def __sql_update_single_data(data: dict):
        return f'update `users` set `length` = {data["length"]}, `register_time` = "{data["register_time"]}", `daily_lock_count` = {data["daily_lock_count"]}, `daily_pk_count` = {data["daily_pk_count"]}, `daily_glue_count` = {data["daily_glue_count"]}, `latest_daily_lock` = "{data["latest_daily_lock"]}", `latest_daily_pk` = "{data["latest_daily_pk"]}", `latest_daily_glue` = "{data["latest_daily_glue"]}", `pk_time` = "{data["pk_time"]}", `pked_time` = "{data["pked_time"]}", `glueing_time` = "{data["glueing_time"]}", `glued_time` = "{data["glued_time"]}", `locked_time` = "{data["locked_time"]}" where `qq` = {_k(data["qq"])};'

    @staticmethod
    def __sql_get_data_counts():
        return "select count(*) from `users`;"

    @staticmethod
    def __sql_order_by_length():
        max = Config.get_config("ranking_list_length")
        return f"select * from `users` order by `length` desc limit {max};"

    @staticmethod
    def __sql_select_batch_data(qqs: list):
        return f"select * from `users` where `qq` in {Sql.utils.tupleify(qqs)};"

    @classmethod
    def get_top_users(cls) -> list:
        sql_ins.cursor.execute(cls.__sql_order_by_length())
        some = sql_ins.cursor.fetchall()
        if not some:
            return None
        return [cls.deserialize(one) for one in some]

    @classmethod
    def get_data_counts(cls) -> int:
        sql_ins.cursor.execute(cls.__sql_get_data_counts())
        one = sql_ins.cursor.fetchone()
        return one[0]

    @classmethod
    def insert_single_data(cls, data: dict):
        sql_ins.cursor.execute(cls.__sql_insert_single_data(data))
        sql_ins.conn.commit()

    @staticmethod
    def deserialize(one: tuple):
        return {
            "qq": one[0],
            "length": one[1],
            "daily_lock_count": one[2],
            "daily_pk_count": one[3],
            "daily_glue_count": one[4],
            "register_time": one[5],
            "latest_daily_lock": one[6],
            "latest_daily_pk": one[7],
            "latest_daily_glue": one[8],
            "pk_time": one[9],
            "pked_time": one[10],
            "glueing_time": one[11],
            "glued_time": one[12],
            "locked_time": one[13],
        }

    @classmethod
    def select_data_by_qq(cls, qq: str):
        sql_ins.cursor.execute(cls.__sql_select_single_data(qq))
        one = sql_ins.cursor.fetchone()
        if one is None:
            return None
        return cls.deserialize(one)

    @classmethod
    def select_batch_data(cls, qqs: list):
        sql_ins.cursor.execute(cls.__sql_select_batch_data(qqs))
        some = sql_ins.cursor.fetchall()
        return [cls.deserialize(one) for one in some]

    @classmethod
    def check_table_exists(cls):
        create_table_funs = [
            [cls.__sql_check_table_exists, cls.__sql_create_table],
            [
                cls.sub_table_info._sql_check_table_exists,
                cls.sub_table_info._sql_create_table,
            ],
            [
                cls.sub_table_rebirth._sql_check_table_exists,
                cls.sub_table_rebirth._sql_create_table,
            ],
            [
                cls.sub_table_badge._sql_check_table_exist,
                cls.sub_table_badge._sql_create_table,
            ],
            [
                cls.sub_table_farm._sql_check_table_exists,
                cls.sub_table_farm._sql_create_table,
            ],
            [
                cls.sub_table_friends._sql_check_table_exists,
                cls.sub_table_friends._sql_create_table,
            ],
        ]
        # check users, info, rebirth table exists
        for funs in create_table_funs:
            sql_ins.cursor.execute(funs[0]())
            one = sql_ins.cursor.fetchone()
            is_table_exists = one[0] == 1
            if not is_table_exists:
                sql_ins.cursor.execute(funs[1]())
                sql_ins.conn.commit()

    @classmethod
    def update_data_by_qq(cls, data: dict):
        sql_ins.cursor.execute(cls.__sql_update_single_data(data))
        sql_ins.conn.commit()

    def destroy(self):
        self.conn.close()


class DB_UserInfo:
    @staticmethod
    def is_user_exists(qq: str):
        sql_ins.cursor.execute(Sql.sub_table_info._sql_select_single_data(qq))
        return sql_ins.cursor.fetchone() is not None

    @classmethod
    def record_user_info(cls, qq: str, data: dict):
        data["qq"] = qq
        is_exists = cls.is_user_exists(qq)
        if is_exists:
            sql_ins.cursor.execute(
                Sql.sub_table_info._sql_update_single_data(data), data
            )
        else:
            sql_ins.cursor.execute(
                Sql.sub_table_info._sql_insert_single_data(data), data
            )
        sql_ins.conn.commit()

    @staticmethod
    def get_batch_user_infos(qqs: list):
        return Sql.sub_table_info.select_batch_data_by_qqs(qqs)

    @staticmethod
    def get_user_info(qq: str):
        return Sql.sub_table_info.select_single_data(qq)


class DataUtils:
    @staticmethod
    def __assign(data_1: dict, data_2: dict):
        return {**data_1, **data_2}

    @staticmethod
    def __make_qq_to_data_map(data: list):
        return {one["qq"]: one for one in data}

    @classmethod
    def merge_data(cls, *datas: list):
        first_data = datas[0]
        if first_data is None:
            first_data = {}
        for i in range(1, len(datas)):
            value = datas[i]
            if value is None:
                continue
            first_data = cls.__assign(first_data, value)
        return first_data

    @classmethod
    def merge_data_list(cls, datas: list):
        maps = [cls.__make_qq_to_data_map(one) for one in datas]
        for key in maps[0].keys():
            for i in range(1, len(maps)):
                if key in maps[i]:
                    maps[0][key] = cls.__assign(maps[0][key], maps[i][key])
        result = []
        for user in datas[0]:
            result.append(maps[0][user["qq"]])
        return result

class DB:

    sub_db_info = DB_UserInfo()
    sub_db_rebirth = DB_Rebirth()
    sub_db_badge = DB_Badge()
    sub_db_farm = DB_Farm()
    sub_db_friends = DB_Friends()

    utils = DataUtils()

    @classmethod
    def make_sure_user_length_not_zero(cls, qq: str):
        """
            解决历史数据有 < 2.8e-17 的问题
        """
        data = cls.load_data(qq)
        if data is None:
            return
        if NumberUtils.is_zero(data['length']):
            data['length'] = 0
            cls.write_data(data)

    @staticmethod
    def create_data(data: dict):
        Sql.insert_single_data(data)

    @staticmethod
    def load_data(qq: str):
        # main data
        user_table_data = Sql.select_data_by_qq(qq)
        if user_table_data is None:
            return None
        # sub data
        rebirth_table_data = Sql.sub_table_rebirth.select_single_data(qq)
        merged_data = DB.utils.merge_data(user_table_data, rebirth_table_data)
        return merged_data

    @classmethod
    def is_registered(cls, qq: str):
        return cls.load_data(qq) is not None

    @classmethod
    def write_data(cls, data: dict):
        Sql.update_data_by_qq(data)

    @staticmethod
    def get_data_counts():
        return Sql.get_data_counts()

    @classmethod
    def length_increase(cls, qq: str, length: float):
        """
        only allow `main.py` call
        """
        user_data = cls.load_data(qq)
        # accuracy
        length_result = NumberUtils.plus(
            user_data["length"], length
        )
        # ensure fixed 2
        length_result = fixed_two_decimal_digits(
            length_result, to_number=True
        )
        user_data["length"] = length_result
        cls.write_data(user_data)

    @classmethod
    def length_decrease(cls, qq: str, length: float):
        """
        only allow `main.py` call
        """
        user_data = cls.load_data(qq)
        will_punish_length = 0
        pure_length = user_data["length"]
        # 不能把转生者打降转
        level = user_data.get("level")
        if level is not None:
            length_view = RebirthSystem_View.get_rebirth_view_by_level(
                level=level, length=pure_length
            )
            pure_length = length_view["pure_length"]
        # TODO: 禁止负值，更好的提示
        if (pure_length - length) < 0:
            will_punish_length = pure_length
        else:
            will_punish_length = length
        will_punish_length = fixed_two_decimal_digits(
            will_punish_length, to_number=True
        )
        # accuracy
        user_data["length"] = NumberUtils.minus(
            user_data["length"], will_punish_length
        )
        cls.write_data(user_data)

    @classmethod
    def record_time(cls, qq: str, key: str):
        user_data = cls.load_data(qq)
        user_data[key] = ArrowUtil.get_now_time()
        cls.write_data(user_data)

    @classmethod
    def reset_daily_count(cls, qq: str, key: str):
        user_data = cls.load_data(qq)
        user_data[key] = 0
        cls.write_data(user_data)

    @classmethod
    def is_lock_daily_limited(cls, qq: str):
        user_data = cls.load_data(qq)
        current_count = user_data["daily_lock_count"]
        is_outed = ArrowUtil.is_date_outed(user_data["latest_daily_lock"])
        if is_outed:
            cls.reset_daily_count(qq, "daily_lock_count")
            return False
        max = Config.get_config("lock_daily_max")
        if current_count >= max:
            return True
        return False

    @classmethod
    def count_lock_daily(cls, qq: str):
        user_data = cls.load_data(qq)
        user_data["daily_lock_count"] += 1
        user_data["latest_daily_lock"] = ArrowUtil.get_now_time()
        cls.write_data(user_data)

    @classmethod
    def is_glue_daily_limited(cls, qq: str):
        user_data = cls.load_data(qq)
        current_count = user_data["daily_glue_count"]
        is_outed = ArrowUtil.is_date_outed(user_data["latest_daily_glue"])
        if is_outed:
            cls.reset_daily_count(qq, "daily_glue_count")
            return False
        max = Config.get_config("glue_daily_max")
        if current_count >= max:
            return True
        return False

    @classmethod
    def count_glue_daily(cls, qq: str):
        user_data = cls.load_data(qq)
        user_data["daily_glue_count"] += 1
        user_data["latest_daily_glue"] = ArrowUtil.get_now_time()
        cls.write_data(user_data)

    @classmethod
    def is_pk_daily_limited(cls, qq: str):
        user_data = cls.load_data(qq)
        current_count = user_data["daily_pk_count"]
        is_outed = ArrowUtil.is_date_outed(user_data["latest_daily_pk"])
        if is_outed:
            cls.reset_daily_count(qq, "daily_pk_count")
            return False
        max = Config.get_config("pk_daily_max")
        if current_count >= max:
            return True
        return False

    @classmethod
    def count_pk_daily(cls, qq: str):
        user_data = cls.load_data(qq)
        user_data["daily_pk_count"] += 1
        user_data["latest_daily_pk"] = ArrowUtil.get_now_time()
        cls.write_data(user_data)

    @classmethod
    def is_pk_protected(cls, qq: str):
        """
        TODO: 对转生者可以刷分，以后需要限制
        """
        user_data = cls.load_data(qq)
        min_length = Config.get_config("pk_guard_chinchin_length")
        if user_data["length"] <= min_length:
            return True
        return False

    @staticmethod
    def get_top_users():
        top_users = Sql.get_top_users()
        qqs = [one["qq"] for one in top_users]
        # info
        info_list = Sql.sub_table_info.select_batch_data_by_qqs(qqs)
        # rebirth
        rebirth_list = Sql.sub_table_rebirth.select_batch_data_by_qqs(qqs)
        # badge
        badge_list = Sql.sub_table_badge.select_batch_data_by_qqs(qqs)
        badge_list_picked = []
        for one in badge_list:
            badge_list_picked.append({"qq": one["qq"], "badge_ids": one["badge_ids"]})
        merged = DB.utils.merge_data_list(
            [top_users, info_list, rebirth_list, badge_list_picked]
        )
        return merged

    @staticmethod
    def get_batch_users(qqs: list):
        return Sql.select_batch_data(qqs)


def init_database(data_dir: Path) -> None:
    """建目录、建六张表、建立（懒）连接。

    幂等：重复调用直接返回。SQLite 路径 = ``data_dir / "data.sqlite"``。
    由 plugin.py 的 on_load 调用（data_dir = ctx.paths.data_dir）。
    """
    global sql_ins, _data_dir
    if sql_ins is not None:
        return
    _data_dir = Path(data_dir)
    _data_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = _data_dir / SQLITE_FILE_NAME
    sqlite_path.touch(exist_ok=True)
    sql_ins = Sql(sqlite_path)
    sql_ins.check_table_exists()


def lazy_init_database() -> None:
    """幂等。message_processor 首行保留调用（原 main.py:82 行为）。

    已初始化则直接返回；若曾被 close_database 关闭，则按 init_database 记住的
    数据目录重连。理论上 plugin.py 的 on_load 保证先于任何消息处理完成初始化，
    此时不连接、不建目录、不抛异常。
    """
    if sql_ins is not None:
        return
    if _data_dir is None:
        return
    init_database(_data_dir)


def close_database() -> None:
    """关闭连接并清空全局 sql_ins；未初始化时为空操作。on_unload 调用。"""
    global sql_ins
    if sql_ins is None:
        return
    sql_ins.destroy()
    sql_ins = None
