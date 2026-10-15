r"""牛子PK 插件入口。

本文件负责：生命周期、配置扁平桥注入、数据库与群开关初始化，以及全部 ``@Command`` 指令注册。
游戏逻辑全部在 ``dicky_pk/game/`` 下，保持全同步代码，详见 ``docs/porting-contract.md``。

指令命中顺序说明（装配工实测结论，2026-10-15，勿改）：
SDK ``collect_components`` 通过 ``dir(instance)`` 收集组件（maibot_sdk/components.py:797），
``dir()`` 按方法名字母序返回；Runner 与 Host 注册全程保序（runner_main.py:1402 →
component_registry.py:919-920），``find_command_by_text`` 按注册序返回第一个
``pattern.search`` 命中（component_registry.py:1109-1121）。**因此 Host 侧命令命中顺序 =
方法名字母序，与源码书写顺序无关**（已用 OneKey env python 跑 ``get_components()`` 验证：
源码序 chinchin→ranking→lock→lock_me，收集序为 chinchin→lock→lock_me→ranking）。

为保证"具体指令优先于兜底指令"且与注册顺序无关，两处重叠 pattern 用否定先行断言解耦：
- ``cmd_lock`` 加 ``(?!我)``：``"锁我..."``（含 ``"锁我 @张三"``）一律归
  ``cmd_lock_me``（``cmd_lock`` 字母序在 ``cmd_lock_me`` 之前，原 NoneBot 版则是
  先注册 ``🔒我`` 后注册 ``🔒``）；
- ``cmd_chinchin`` 加否定断言：``"牛子排名/牛子帮助/..."`` 等具体指令（含带尾随空白/
  at 的写法）不会被 ``^牛子`` 兜底吞掉（``cmd_chinchin`` 字母序早于全部 ``牛子xxx``
  具体指令）；剩下 ``"牛子 排名"``/``"牛子仙境abc"`` 这类纯模糊写法才由兜底接手，
  并在 handler 里归一化后交给 message_processor 的 startswith 模糊匹配。

另：锚定指令的 pattern 一律以 ``(?:\s|$)`` 收尾而非裸 ``$``——Host 交给
``compiled_pattern.search`` 的文本是未 strip 的 ``processed_plain_text``
（bot.py:277），尾随空白很常见；at 段在其中渲染为 ``"@昵称"`` 且以空格连接
（message.py:172/360-390），``"注册牛子 @张三"`` 这类输入用裸 ``$`` 永远无法命中，
而原版 on_command 只要求消息以命令名开头。带 at 的指令（关注牛子/取关牛友/看他牛子/
pk/🔒/打胶）pattern 本就不带结尾锚，行为一致。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from maibot_sdk import Command, MaiBotPlugin

from .config import DickyPKConfig
from .game import db as game_db
from .game import enable as game_enable
from .game.badge import BadgeSystem
from .game.config import Config, flatten_config
from .game.farm import FarmSystem
from .game.friends import FriendsSystem
from .game.main import KEYWORDS, message_processor
from .game.utils import create_match_func_factory

logger = logging.getLogger(__name__)

# 私聊拒绝文案（决策②：私聊只读白名单之外的指令一律拒绝）
PRIVATE_REJECT_MESSAGE = "该指令仅在和机器人的群聊中使用（私聊可查询：牛子、牛子排名、牛子成就、牛友、牛子帮助）"
# at 缺失提示
AT_REQUIRED_MESSAGE = "请 @ 一个用户"
# 运行异常提示
RUNTIME_ERROR_MESSAGE = "牛子秘境波动，请稍后再试"
# 昵称缺省值
DEFAULT_NICKNAME = "无名英雄"
# 游戏未启用时的占位响应；intercept=0 让消息继续走 AI，等价原版 block=False
GAME_DISABLED_RESPONSE = "游戏未启用"

# message_processor 内部的关键词匹配顺序（game/main.py:143-227，逐项对齐）：
# 归一化后的 "牛子<参数>" 文本实际落到哪个指令，由该顺序 + startswith 模糊匹配决定。
_KEYWORD_DISPATCH_ORDER = (
    "help",
    "sign_up",
    "farm",
    "farm_start",
    "ranking",
    "badge",
    "rebirth",
    "friends",
    "chinchin",
)
# 私聊只读白名单（决策②）对应的 KEYWORDS 键
_READONLY_KEYWORDS = frozenset({"help", "ranking", "badge", "friends", "chinchin"})


def _is_private_readonly_message(message_text: str) -> bool:
    """判断 message_processor 实际会命中的指令是否属于私聊只读白名单。

    仅 cmd_chinchin 的 "牛子<参数>" 归一化路径使用：原版该变体经
    ``dicky_run('牛子' + msg)`` 可直达转生/仙境/修炼等群聊专属指令
    （原版 __init__.py:108），移植版必须保证这些指令在私聊门下被拒绝，
    而不是被 cmd_chinchin 的 read_only 白名单放行。
    """
    match_func = create_match_func_factory(fuzzy=True)
    for key in _KEYWORD_DISPATCH_ORDER:
        if match_func(KEYWORDS.get(key), message_text):
            return key in _READONLY_KEYWORDS
    # 未命中任何关键词时理论上不可达（"牛子" 兜底必中）；保守按只读放行。
    return True


class DickyPKPlugin(MaiBotPlugin):
    """牛子PK 群聊小游戏插件。"""

    config_model = DickyPKConfig

    async def on_load(self) -> None:
        """插件加载：注入扁平配置，初始化数据库与群开关状态。"""
        # 兜底：Runner 正常会在 on_load 之前完成配置注入
        # （runner_main.py: _prepare_plugin_activation -> _apply_plugin_config，先于 _invoke_plugin_on_load）；
        # 若实例被脱离 Runner 直接构造，则回退默认配置，保证 self.config 可用。
        # 注意：不能无条件调用 set_plugin_config(build_default_config())，否则会覆盖用户 config.toml。
        try:
            _ = self.config
        except Exception:
            self.set_plugin_config(self.build_default_config())

        # 强类型配置 -> 扁平字典（原 config.json 键形）-> 游戏逻辑配置桥
        Config.init(flatten_config(self.config))
        # 数据库（六张表，懒连接；路径 <data_dir>/data.sqlite）
        game_db.init_database(self.ctx.paths.data_dir)
        # 群开关状态（<data_dir>/enable.json）
        game_enable.init(self.ctx.paths.data_dir)
        logger.info("牛子PK 插件已加载")

    async def on_unload(self) -> None:
        """插件卸载：关闭数据库连接。"""
        game_db.close_database()
        logger.info("牛子PK 插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        """配置热更新：scope == "self" 时重新拍扁并注入游戏逻辑。"""
        del config_data
        del version
        if scope == "self":
            # Runner 已在调用本方法前完成 set_plugin_config（runner_main.py: _handle_config_updated）
            Config.init(flatten_config(self.config))
            # badge/farm/friends 三个系统有模块级 cache（移植契约 §2.5），必须在此失效，
            # 否则 BadgeSystem/FarmSystem/FriendsSystem 仍读旧配置对象。
            BadgeSystem.reset_cache()
            FarmSystem.reset_cache()
            FriendsSystem.reset_cache()
            logger.info("牛子PK 配置已热更新：扁平配置桥与三个系统缓存已刷新")

    # ===== 内部助手 =====

    async def _run_game(
        self,
        message_text: str,
        kwargs: dict[str, Any],
        *,
        read_only: bool = False,
        require_at: bool = False,
    ) -> tuple[bool, str, int]:
        """游戏指令统一入口：门禁 -> at 提取 -> message_processor -> 逐条发送。

        Args:
            message_text: 传给 message_processor 的消息（具体指令传规范键，牛子传原始 text）。
            kwargs: Host 下发的命令参数（text/stream_id/group_id/platform/user_id/message/...）。
            read_only: 是否私聊只读指令（决策② 白名单内的五件套 + 帮助）。
            require_at: 是否必须 @ 一个用户。

        Returns:
            tuple[bool, str, int]: ``(success, response, intercept)``；intercept=0 表示
            消息继续走 AI（等价原版 block=False），2 表示拦截。
        """
        raw_message = kwargs.get("message")
        message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
        platform = str(kwargs.get("platform") or "")
        user_id = str(kwargs.get("user_id") or "")
        group_id = str(kwargs.get("group_id") or "")
        stream_id = str(kwargs.get("stream_id") or "")
        try:
            if not platform or not user_id:
                # 缺少身份信息，无法构造复合键，静默放过
                return True, "", 2

            # 1) 群/私聊门禁：group_id 为空即私聊
            if not group_id and not read_only:
                await self.ctx.send.text(PRIVATE_REJECT_MESSAGE, stream_id)
                return True, PRIVATE_REJECT_MESSAGE, 2

            # 2) 游戏开关门禁（保持原版行为：未开不回复，消息继续走 AI）
            if not game_enable.is_all_enabled():
                return True, GAME_DISABLED_RESPONSE, 0
            if group_id and not game_enable.is_group_enabled(group_id):
                return True, GAME_DISABLED_RESPONSE, 0

            # 3) at 门禁
            user_key = f"{platform}:{user_id}"
            at_key: str | None = None
            for seg in message.get("raw_message") or []:
                if isinstance(seg, dict) and seg.get("type") == "at":
                    target = (seg.get("data") or {}).get("target_user_id")
                    if target:
                        at_key = f"{platform}:{target}"
                    break
            if require_at and not at_key:
                await self.ctx.send.text(AT_REQUIRED_MESSAGE, stream_id)
                return True, AT_REQUIRED_MESSAGE, 2

            # 4) 组装上下文并跑游戏逻辑（全同步）
            user_info = (message.get("message_info") or {}).get("user_info") or {}
            nickname = (
                user_info.get("user_cardname") or user_info.get("user_nickname") or DEFAULT_NICKNAME
            )
            buffer: list[str] = []
            message_processor(message_text, user_key, group_id, at_key, nickname, buffer)
            last_reply = ""
            for item in buffer:
                text = str(item)
                if not text:
                    continue
                await self.ctx.send.text(text, stream_id)
                last_reply = text

            # 5) 统一返回
            return True, last_reply, 2
        except Exception as exc:
            self.ctx.logger.error(f"牛子PK 指令执行失败: {exc}", exc_info=True)
            try:
                await self.ctx.send.text(RUNTIME_ERROR_MESSAGE, stream_id)
            except Exception:
                pass
            return False, str(exc), 2

    async def _run_switch(
        self,
        kwargs: dict[str, Any],
        action: Callable[[str], str],
    ) -> tuple[bool, str, int]:
        """开关指令统一入口（不走 _run_game，本身不受游戏开关门禁限制）。

        Args:
            kwargs: Host 下发的命令参数。
            action: 同步开关逻辑，入参为群号（私聊为空串），返回回复文案（空串表示不回复）。

        Returns:
            tuple[bool, str, int]: ``(success, response, intercept)``。
        """
        stream_id = str(kwargs.get("stream_id") or "")
        group_id = str(kwargs.get("group_id") or "")
        try:
            reply = action(group_id)
            if reply:
                await self.ctx.send.text(reply, stream_id)
            return True, reply, 2
        except Exception as exc:
            self.ctx.logger.error(f"牛子PK 开关指令执行失败: {exc}", exc_info=True)
            try:
                await self.ctx.send.text(RUNTIME_ERROR_MESSAGE, stream_id)
            except Exception:
                pass
            return False, str(exc), 2

    # ===== 开关指令（operator；1-4）=====

    @Command("enable_all", description="开启牛子秘境（总开关）", pattern=r"^开启牛子秘境(?:\s|$)", permission="operator")
    async def cmd_enable_all(self, **kwargs: Any) -> tuple[bool, str, int]:
        """开启牛子秘境：总开关置 True；群聊同时在本群启用牛子pk。"""

        def action(group_id: str) -> str:
            if group_id:
                game_enable.set_enable(group_id, True)
            game_enable.set_all_enable(True)
            reply = "牛子秘境已开启."
            if group_id:
                reply += "\n已在本群启用牛子pk"
            return reply

        return await self._run_switch(kwargs, action)

    @Command("disable_all", description="关闭牛子秘境（总开关）", pattern=r"^关闭牛子秘境(?:\s|$)", permission="operator")
    async def cmd_disable_all(self, **kwargs: Any) -> tuple[bool, str, int]:
        """关闭牛子秘境：清空群列表，总开关置 False。"""

        def action(group_id: str) -> str:
            del group_id  # 关闭秘境是全站的，与原版一致
            game_enable.clear_groups()
            game_enable.set_all_enable(False)
            return "牛子秘境已关闭."

        return await self._run_switch(kwargs, action)

    @Command(
        "enable_group",
        description="在本群启用牛子pk",
        pattern=r"^(?:启用|开启)(?:牛子pk|dicky-pk)(?:\s|$)",
        permission="operator",
    )
    async def cmd_enable_group(self, **kwargs: Any) -> tuple[bool, str, int]:
        """启用本群牛子pk：秘境未开时提示，否则开启群开关。"""
        group_id = str(kwargs.get("group_id") or "")
        if not group_id:
            await self.ctx.send.text(PRIVATE_REJECT_MESSAGE, str(kwargs.get("stream_id") or ""))
            return True, PRIVATE_REJECT_MESSAGE, 2

        def action(gid: str) -> str:
            if not game_enable.is_all_enabled():
                return "牛子秘境尚未开启"
            game_enable.set_enable(gid, True)
            return "已启用群聊小游戏: Dicky-PK"

        return await self._run_switch(kwargs, action)

    @Command(
        "disable_group",
        description="在本群禁用牛子pk",
        pattern=r"^(?:禁用|关闭)(?:牛子pk|dicky-pk)(?:\s|$)",
        permission="operator",
    )
    async def cmd_disable_group(self, **kwargs: Any) -> tuple[bool, str, int]:
        """禁用本群牛子pk：秘境未开时提示，否则关闭群开关。"""
        group_id = str(kwargs.get("group_id") or "")
        if not group_id:
            await self.ctx.send.text(PRIVATE_REJECT_MESSAGE, str(kwargs.get("stream_id") or ""))
            return True, PRIVATE_REJECT_MESSAGE, 2

        def action(gid: str) -> str:
            if not game_enable.is_all_enabled():
                return "牛子秘境尚未开启"
            game_enable.set_enable(gid, False)
            return "已禁用群聊小游戏: Dicky-PK"

        return await self._run_switch(kwargs, action)

    # ===== 游戏指令（5-20）=====

    @Command("help", description="牛子PK 指令帮助", pattern=r"^牛子帮助(?:\s|$)")
    async def cmd_help(self, **kwargs: Any) -> tuple[bool, str, int]:
        """牛子帮助（私聊只读白名单内）。"""
        return await self._run_game("牛子帮助", kwargs, read_only=True)

    @Command("sign_up", description="注册一只牛子", pattern=r"^注册牛子(?:\s|$)")
    async def cmd_sign_up(self, **kwargs: Any) -> tuple[bool, str, int]:
        """注册牛子（仅群聊）。"""
        return await self._run_game("注册牛子", kwargs)

    @Command("farm_info", description="查看牛子仙境", pattern=r"^牛子仙境(?:\s|$)")
    async def cmd_farm_info(self, **kwargs: Any) -> tuple[bool, str, int]:
        """牛子仙境（仅群聊）。"""
        return await self._run_game("牛子仙境", kwargs)

    @Command("farm_start", description="牛子仙境修炼", pattern=r"^牛子(?:修炼|练功|修仙)(?:\s|$)")
    async def cmd_farm_start(self, **kwargs: Any) -> tuple[bool, str, int]:
        """牛子修炼/练功/修仙（仅群聊）。"""
        return await self._run_game("牛子修炼", kwargs)

    @Command("ranking", description="牛子排名", pattern=r"^牛子(?:排名|排行)(?:\s|$)")
    async def cmd_ranking(self, **kwargs: Any) -> tuple[bool, str, int]:
        """牛子排名/排行（私聊只读白名单内）。"""
        return await self._run_game("牛子排名", kwargs, read_only=True)

    @Command("badge", description="牛子成就", pattern=r"^牛子成就(?:\s|$)")
    async def cmd_badge(self, **kwargs: Any) -> tuple[bool, str, int]:
        """牛子成就（私聊只读白名单内）。"""
        return await self._run_game("牛子成就", kwargs, read_only=True)

    @Command("rebirth", description="牛子转生", pattern=r"^牛子转生(?:\s|$)")
    async def cmd_rebirth(self, **kwargs: Any) -> tuple[bool, str, int]:
        """牛子转生（仅群聊）。"""
        return await self._run_game("牛子转生", kwargs)

    # 注意：pattern 必须是 "^(牛友|牛子好友|牛子朋友)$"（与原版 on_command('牛友') 一致）；
    # 不能写成 "^牛子(友|子好友|子朋友)$"——那样连主形式 "牛友" 都匹配不上。
    @Command("friends", description="牛友系统", pattern=r"^(?:牛友|牛子好友|牛子朋友)(?:\s|$)")
    async def cmd_friends(self, **kwargs: Any) -> tuple[bool, str, int]:
        """牛友/牛子好友/牛子朋友（私聊只读白名单内）。"""
        return await self._run_game("牛友", kwargs, read_only=True)

    @Command("friends_add", description="关注牛友（需 @ 用户）", pattern=r"^(关注牛子|添加牛友|添加朋友)")
    async def cmd_friends_add(self, **kwargs: Any) -> tuple[bool, str, int]:
        """关注牛子/添加牛友/添加朋友（仅群聊，必须 at）。"""
        return await self._run_game("关注牛子", kwargs, require_at=True)

    @Command("friends_delete", description="取关牛友（需 @ 用户）", pattern=r"^(取关牛子|删除牛友|删除朋友)")
    async def cmd_friends_delete(self, **kwargs: Any) -> tuple[bool, str, int]:
        """取关牛子/删除牛友/删除朋友（仅群聊，必须 at）。"""
        return await self._run_game("取关牛子", kwargs, require_at=True)

    @Command("see_chinchin", description="看他牛子（需 @ 用户）", pattern=r"^(看他牛子|看看牛子)")
    async def cmd_see_chinchin(self, **kwargs: Any) -> tuple[bool, str, int]:
        """看他牛子/看看牛子（仅群聊，必须 at）。"""
        return await self._run_game("看他牛子", kwargs, require_at=True)

    @Command("pk", description="牛子PK（需 @ 用户）", pattern=r"^pk")
    async def cmd_pk(self, **kwargs: Any) -> tuple[bool, str, int]:
        """pk（仅群聊，必须 at）。"""
        return await self._run_game("pk", kwargs, require_at=True)

    @Command("lock_me", description="🔒 自己", pattern=r"^(?:🔒|suo|嗦|锁)我")
    async def cmd_lock_me(self, **kwargs: Any) -> tuple[bool, str, int]:
        """🔒我/suo我/嗦我/锁我（仅群聊；"X我..." 一律归本指令，复刻原版
        on_command('🔒我') 的前缀匹配语义，原版 __init__.py:122-127）。"""
        return await self._run_game("🔒我", kwargs)

    @Command("lock", description="🔒 他人（可 @ 用户）", pattern=r"^(?:🔒|suo|嗦|锁)(?!我)")
    async def cmd_lock(self, **kwargs: Any) -> tuple[bool, str, int]:
        """🔒/suo/嗦/锁 @用户（仅群聊，at 可选；"X我" 由 cmd_lock_me 处理）。"""
        return await self._run_game("🔒", kwargs)

    @Command("glue", description="打胶", pattern=r"^打胶")
    async def cmd_glue(self, **kwargs: Any) -> tuple[bool, str, int]:
        """打胶（仅群聊，at 可选）。"""
        return await self._run_game("打胶", kwargs)

    @Command(
        "chinchin",
        description="查询自己的牛子（牛子兜底指令）",
        pattern=r"^牛子(?!(?:帮助|仙境|修炼|练功|修仙|排名|排行|成就|转生|好友|朋友)(?:\s|$))",
    )
    async def cmd_chinchin(self, **kwargs: Any) -> tuple[bool, str, int]:
        """牛子（兜底，私聊只读白名单内）。

        复刻原版 ``牛子`` 指令的 ``'牛子' + arg`` 拼接语义（原版 __init__.py:106-108：
        ``dicky_run('牛子'+msg, ...)``）：text 去掉开头 "牛子" 后剥掉前缀空白再回填，
        因此 ``牛子 排名`` → ``牛子排名`` → entry_ranking，``牛子 转生`` → ``牛子转生``
        → entry_rebirth，全部带空格变体与原版一致。

        归一化后文本可能落到群聊专属指令（转生/仙境/修炼/注册…）。私聊门下按归一化后
        实际命中的指令重新判定 read_only：非白名单指令一律拒绝（决策②），避免
        ``牛子 转生`` 之类输入绕过私聊只读限制。
        """
        text = str(kwargs.get("text") or "")
        message_text = text
        if text.startswith("牛子"):
            rest = text[len("牛子") :].lstrip()
            if rest:
                message_text = "牛子" + rest
        read_only = True
        if not str(kwargs.get("group_id") or ""):
            read_only = _is_private_readonly_message(message_text)
        return await self._run_game(message_text, kwargs, read_only=read_only)


def create_plugin() -> DickyPKPlugin:
    """创建插件实例。"""
    return DickyPKPlugin()
