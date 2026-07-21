from mcp.types import CallToolResult
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from typing import Optional

from ..make_enka import list_roles_dict
from ..ysenka import (
    enka_card,
    enka_card_cloud,
    resolve_character,
    resolve_character_alias_with_llm,
)


@dataclass
class kapian(FunctionTool):
    enable_llm_character_alias: bool = True
    enable_local_card: bool = True
    name: str = "genshin_card"
    description: str = (
        "当用户想要查看、生成、发送原神角色卡片图片或角色面板图片时调用。"
        "例如：‘看一下原神269377658的万叶’、‘查看原神269377658的万叶’、"
        "‘发我这个 UID 的万叶面板’或‘生成万叶角色卡片’。"
        "指定角色后，本工具会直接发送对应的角色卡片图片。"
        "如果用户明确询问配装数值、武器、圣遗物、命座或属性分析，才调用 genshin_character_info。"
        "仅传入 UID 时查询角色列表（含角色名、元素、等级）；"
        "character 可使用角色序号、完整名称或简称。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "原神玩家 UID",
                },
                "character": {
                    "type": "string",
                    "description": "角色序号、完整名称或简称（可选），不填则返回全部角色列表",
                },
            },
            "required": ["uid"],
        }
    )

    async def call(
        self,
        context: ContextWrapper[AstrAgentContext],
        uid: str = "",
        character: Optional[str] = None,
        character_index: Optional[int] = None,
    ) -> str | CallToolResult:
        if not uid:
            return "请提供原神玩家 UID。"

        # character_index 保留用于兼容此前直接调用工具的代码。
        character_selector = character if character not in (None, "") else character_index

        if character_selector is None:
            try:
                roles = await list_roles_dict(str(uid))
            except ValueError as e:
                return f"查询失败：{e}"
            if not roles:
                return f"未查询到 UID {uid} 的角色信息，可能该玩家未公开角色展柜。"
            lines = []
            for i, role in enumerate(roles):
                lines.append(f"{i + 1}. {role['name']} | 元素：{role['ele']} | 等级：{role['lvl']}")
            return f"UID {uid} 的角色列表：\n" + "\n".join(lines)
        else:
            try:
                try:
                    astr_context = context.context.context
                    event = context.context.event
                except AttributeError:
                    return "无法取得当前消息事件，暂时不能发送角色卡片。"

                async def llm_alias_resolver(selector_text, roles):
                    if not self.enable_llm_character_alias:
                        return None
                    return await resolve_character_alias_with_llm(
                        astr_context,
                        event,
                        selector_text,
                        roles,
                    )

                character_index, role = await resolve_character(
                    str(uid),
                    character_selector,
                    alias_resolver=llm_alias_resolver,
                )
                await event.send(
                    event.plain_result(
                        f"正在生成 UID {uid} 的角色 {role['name']} "
                        f"（序号 {character_index}）卡片..."
                    )
                )

                if self.enable_local_card:
                    image_result = await enka_card(
                        str(uid),
                        character_index,
                        avatar_id=role["id"],
                    )
                else:
                    image_result = await enka_card_cloud(str(uid), role["id"])
            except ValueError as e:
                return f"无法识别角色：{e}"
            except Exception as e:
                return f"生成卡片时发生错误：{e}"

            if isinstance(image_result, str) and image_result.startswith("ERROR:"):
                return f"生成卡片失败：{image_result[6:]}"

            try:
                await event.send(event.image_result(image_result))
            except Exception as e:
                return f"卡片已生成，但直接发送图片失败：{str(e)}"

            return (
                f"UID {uid} 的角色 {role['name']}（序号 {character_index}）卡片"
                "已直接发送给用户，无需再调用 send_message_to_user。"
            )
