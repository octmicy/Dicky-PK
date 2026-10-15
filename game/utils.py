"""工具层（从原版 ``src/utils.py`` 移植）。

- ``join`` / ``fixed_two_decimal_digits`` / ``create_match_func_factory`` /
  ``get_object_values`` / ``is_number`` / ``Random`` / ``NumberUtils`` 逐字保留；
- ``ArrowUtil`` 以标准库 ``datetime`` + ``zoneinfo("Asia/Shanghai")`` 重写，
  方法签名与数值语义和原版 arrow 实现一致（移植契约 §7.1 逐条对照）；
- 原模块级 ``arrow_now`` / ``arrow_get`` 按契约删除，改为模块私有 ``_now`` / ``_get``；
  跨模块时间比较一律走 ``ArrowUtil``，业务代码不许直接调 ``datetime.now()``（§5.4）。
"""

import random
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# 全工程统一时区与时间字符串格式（移植契约 §5.4）
TZ = ZoneInfo("Asia/Shanghai")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _now():
    """等价于原版 ``arrow.now(tz="Asia/Shanghai")``。"""
    return datetime.now(TZ)


def _get(time: str):
    """等价于原版 ``arrow.get(time, tzinfo="Asia/Shanghai")``：把 naive 字符串当北京时间解析。"""
    return datetime.strptime(time.strip(), TIME_FORMAT).replace(tzinfo=TZ)


def join(arr: list, sep: str = ""):
    # filter all empty value
    arr = list(filter(lambda x: x, arr))
    return sep.join(arr)


def fixed_two_decimal_digits(num: int, to_number: bool = False):
    result = "{:.2f}".format(num)
    if to_number:
        return float(result)
    return result


def create_match_func_factory(fuzzy: bool = False):
    def is_keyword_matched(keywords: list, text: str):
        for keyword in keywords:
            if fuzzy:
                if text.startswith(keyword):
                    return True
            else:
                if text == keyword:
                    return True
        return False

    return is_keyword_matched


def get_object_values(obj: dict):
    vs = obj.values()
    ret = []
    for v in vs:
        if isinstance(v, list):
            ret.extend(v)
        else:
            ret.append(v)
    return ret


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass


class ArrowUtil:
    @staticmethod
    def is_date_outed(time: str):
        return _get(time).date() != _now().date()

    @staticmethod
    def get_arrow_gap_timestamp(time_1: str, time_2: str):
        return int(_get(time_1).timestamp()) - int(_get(time_2).timestamp())

    @classmethod
    def get_arrow_gap_minutes(cls, time_1: str, time_2: str):
        return cls.get_arrow_gap_timestamp(time_1, time_2) / 60

    @staticmethod
    def complete_date_with_today_from_h_s(text: str):
        """
        10:00 -> 2020-01-01 10:00:00
        """
        return f'{_now().strftime("%Y-%m-%d")} {text.strip()}:00'

    @staticmethod
    def is_now_in_time_range(start: str, end: str):
        """
        start/end: YYYY-MM-DD HH:mm:ss
        """
        start_timestamp = int(_get(start).timestamp())
        end_timestamp = int(_get(end).timestamp())
        now_timestamp = int(_now().timestamp())
        return start_timestamp <= now_timestamp <= end_timestamp

    @staticmethod
    def get_time_with_shift(time: str, shift_mins: int = 0, shift_days: int = 0):
        """
        start_time: YYYY-MM-DD HH:mm:ss
        duration: minutes
        """
        if shift_days:
            shift_mins += shift_days * 24 * 60
        return (_get(time) + timedelta(minutes=shift_mins)).strftime(TIME_FORMAT)

    @staticmethod
    def lt(time_1: str, time_2: str):
        return int(_get(time_1).timestamp()) < int(_get(time_2).timestamp())

    @staticmethod
    def get_now_time():
        return _now().strftime(TIME_FORMAT)

    @staticmethod
    def calc_diff_minutes(time_1: str, time_2: str):
        # 注意：必须保持原版 int(a / b) 向零截断，不能用 //（负数结果不同）
        return int(
            (int(_get(time_1).timestamp()) - int(_get(time_2).timestamp())) / 60
        )

    @staticmethod
    def date_improve(time: str):
        ins = _get(time)
        is_today = ins.date() == _now().date()
        if is_today:
            return ins.strftime("%H:%M")
        is_this_year = ins.year == _now().year
        if is_this_year:
            return ins.strftime("%m-%d %H:%M")
        return ins.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def get_time_diff_days(time_1: str, time_2: str):
        """
        time_1 - time_2
        """
        # 原版先把两侧 format("YYYY-MM-DD") 截断到日期再相减
        # （arrow.get 支持 "YYYY-MM-DD" 解析为当日零点）；这里等价地归到当日 00:00:00。
        # 同样保持 int(a / b) 向零截断，不用 //。
        date_1 = _get(time_1).replace(hour=0, minute=0, second=0, microsecond=0)
        date_2 = _get(time_2).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(
            (int(date_1.timestamp()) - int(date_2.timestamp()))
            / (60 * 60 * 24)
        )


class Random:

    nums = []
    max_nums = 500

    @staticmethod
    def get_secure_random_number():
        cryptogen = random.SystemRandom()
        return cryptogen.random()

    @staticmethod
    def generate_secure_random_number():
        return secrets.randbits(256) / ((1 << 256) - 1)

    @classmethod
    def get_single_random(cls):
        # num_1 = cls.generate_secure_random_number()
        num_2 = cls.generate_secure_random_number()
        return num_2

    @classmethod
    def fill(cls):
        while len(cls.nums) < cls.max_nums:
            cls.nums.append(cls.get_single_random())

    @classmethod
    def random(cls):
        if len(cls.nums) == 0:
            cls.fill()
        return cls.nums.pop()

class NumberUtils():

    @classmethod
    def plus(cls, a: float, b: float):
        ret = Decimal(a) + Decimal(b)
        if cls.is_zero(ret):
            return 0
        return float(ret)
    
    @classmethod
    def minus(cls, a: float, b: float):
        ret = Decimal(a) - Decimal(b)
        if cls.is_zero(ret):
            return 0
        return float(ret)
    
    @staticmethod
    def is_zero(a: float):
        return Decimal(a).quantize(Decimal('0.000')) == 0
