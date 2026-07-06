from mcp.types import CallToolResult
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from typing import Optional

from ..make_enka import list_roles_dict
from ..ysenka import enka_card


@dataclass
class kapian(FunctionTool):
    name: str = "genshin_card"
    description: str = (
        "获取原神玩家角色信息或生成角色卡片。传入 UID 查询角色列表（含角色名、元素、等级）；"
        "也可指定 character_index 生成对应角色的详细卡片。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "原神玩家 UID",
                },
                "character_index": {
                    "type": "integer",
                    "description": "角色编号（可选，从 1 开始），不填则返回全部角色列表",
                },
            },
            "required": ["uid"],
        }
    )

    async def call(
        self,
        context: ContextWrapper[AstrAgentContext],
        uid: str = "",
        character_index: Optional[int] = None,
    ) -> str | CallToolResult:
        if not uid:
            return "请提供原神玩家 UID。"

        if character_index is None:
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
                image_path = await enka_card(str(uid), int(character_index))
            except Exception as e:
                return f"生成卡片时发生错误：{e}"
            if isinstance(image_path, str) and image_path.startswith("ERROR:"):
                return f"生成卡片失败：{image_path[6:]}"
            return f"已成功生成 UID {uid} 第 {character_index} 个角色的卡片，图片路径：{image_path}"
