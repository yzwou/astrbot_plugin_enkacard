from mcp.types import CallToolResult
from pydantic import Field
from astrbot.api import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic.dataclasses import dataclass
from typing import Optional

@dataclass
class kapian(FunctionTool):
