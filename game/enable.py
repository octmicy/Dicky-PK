"""群开关状态管理。

移植自原版 ``nonebot_plugin_dicky_pk/__init__.py`` 的 ``enablelist`` 逻辑：

- 存储文件：``<ctx.paths.data_dir>/enable.json``；
- 结构：``{"all": bool, "group": [str]}``，``all`` 为牛子秘境总开关，``group`` 为启用 pk 的群列表；
- 修复了原版 ``set_enable`` 开启时不去重的 bug（原版 ``list(set(...))`` 的结果被丢弃，
  重复开启同一群会写入重复群号）。

门禁规则（详见移植契约）：
- 群聊指令：``is_all_enabled()`` 且 ``is_group_enabled(group_id)`` 才放行；
- 私聊只读指令：仅要求 ``is_all_enabled()``（没有群可开）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ENABLE_FILE_NAME = "enable.json"

_DEFAULT_STATE: dict[str, Any] = {"all": False, "group": []}

_state: dict[str, Any] | None = None
_file_path: Path | None = None


def init(data_dir: Path) -> None:
    """初始化开关状态：定位数据文件并加载；文件不存在时落盘默认值。"""
    global _file_path, _state
    _file_path = Path(data_dir) / ENABLE_FILE_NAME
    file_existed = _file_path.is_file()
    _state = _read_file(_file_path)
    if not file_existed:
        save()
    logger.info("牛子PK 群开关状态已加载: all=%s, groups=%d", _state["all"], len(_state["group"]))


def _read_file(file_path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _default_state()
    return _normalize(raw)


def _default_state() -> dict[str, Any]:
    return {"all": bool(_DEFAULT_STATE["all"]), "group": list(_DEFAULT_STATE["group"])}


def _normalize(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return _default_state()
    groups: list[str] = []
    group_raw = raw.get("group", [])
    if isinstance(group_raw, list):
        for group in group_raw:
            group_id = str(group).strip()
            if group_id and group_id not in groups:
                groups.append(group_id)
    return {"all": bool(raw.get("all", False)), "group": groups}


def load() -> dict[str, Any]:
    """从磁盘加载开关状态（``init`` 之前调用时懒加载，未初始化则返回默认值）。"""
    global _state
    if _state is None:
        if _file_path is None:
            _state = _default_state()
        else:
            _state = _read_file(_file_path)
    return _state


def save() -> None:
    """把当前开关状态写回磁盘。"""
    if _file_path is None or _state is None:
        return
    _file_path.parent.mkdir(parents=True, exist_ok=True)
    _file_path.write_text(
        json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def set_enable(group_id: str, en: bool) -> None:
    """开启/关闭指定群的牛子pk（开启时去重，修复原版重复添加 bug）。"""
    state = load()
    gid = str(group_id)
    if en:
        if gid not in state["group"]:
            state["group"].append(gid)
    else:
        state["group"] = [group for group in state["group"] if group != gid]
    save()


def set_all_enable(en: bool) -> None:
    """开启/关闭牛子秘境总开关（对应原版 开启牛子秘境/关闭牛子秘境 指令）。"""
    state = load()
    state["all"] = bool(en)
    save()


def clear_groups() -> None:
    """清空群列表（关闭牛子秘境时调用，与原版行为一致）。"""
    state = load()
    state["group"] = []
    save()


def is_group_enabled(group_id: str) -> bool:
    """指定群是否启用了牛子pk。"""
    return str(group_id) in load()["group"]


def is_all_enabled() -> bool:
    """牛子秘境总开关是否开启。"""
    return bool(load()["all"])
