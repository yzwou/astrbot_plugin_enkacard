import asyncio
import os
from pathlib import Path

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


from .ysenka import *
from .generate_role_list import role_list_img
from .make_enka import list_roles_dict

from .tools.kapian import kapian

ENKA_CARD_API_URL = "https://enkacard-spider-nuulvlmavw.ap-southeast-1.fcapp.run"

@register("astrbot_plugin_enkacard", "yzwou", "获取指定原神玩家信息的插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.enable_local_blender = self.config.get("enable_local_blender", False)
        self.enable_local_card = self.config.get("enable_local_card", True)
        self.PLUGIN_NAME = "astrbot_plugin_enkacard"
        self.context.add_llm_tools(kapian())

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        plugin_data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.PLUGIN_NAME
        plugin_data_path.mkdir(parents=True, exist_ok=True)

        first_run_flag = plugin_data_path / ".initialized"
        if not first_run_flag.exists():
            await self._on_first_run(plugin_data_path)

    async def _on_first_run(self, plugin_data_path: Path):
        """插件首次运行时执行，仅调用一次。"""
        logger.info(f"{self.PLUGIN_NAME} 首次运行，执行初始化...")
        try:
            await enka_update()
        except Exception as e:
            logger.error(f"初始化失败：{e}")
            return
        logger.info(f"{self.PLUGIN_NAME} 初始化完成")
        (plugin_data_path / ".initialized").touch()

    @filter.command("ysupdate")
    async def ysupdate(self, event: AstrMessageEvent):
        """手动触发 enka 数据更新。"""
        plugin_data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.PLUGIN_NAME
        yield event.plain_result("正在更新 enka 数据...")
        try:
            await enka_update()
        except Exception as e:
            logger.error(f"更新失败：{e}")
            yield event.plain_result(f"❌ 更新失败：{e}")
            return
        (plugin_data_path / ".initialized").touch()
        yield event.plain_result("✅ 更新完成")



    @filter.command("ys")
    async def character_card(self, event: AstrMessageEvent, uid: str = None, character_index: int = None):
        """获取原神角色卡片图片。用法: /ys [uid] [角色编号（选填）]"""
        if not uid:
            yield event.plain_result("用法: /ys [uid] [角色编号（选填）]\n示例: /ys 269377658 1")
            return

        if character_index is None:
            try:
                if not self.enable_local_blender:
                    html_file_path = await role_list_img(uid, False)

                    # 检查是否返回错误信息
                    if isinstance(html_file_path, str) and html_file_path.startswith("ERROR:"):
                        error_msg = html_file_path[6:]  # 移除 "ERROR:" 前缀
                        logger.error(f"角色列表生成失败 | UID: {uid} | 错误: {error_msg}")
                        yield event.plain_result(f"❌ {error_msg}")
                        return

                    options = {
                        "type": "jpeg",
                        "quality": 100
                    }
                    with open(html_file_path, 'r', encoding='utf-8') as f:
                        TMPL = f.read()
                    url = await self.html_render(TMPL, {}, options=options)

                    logger.info(f"使用API渲染图片生成成功 | {url}")
                    yield event.image_result(url)
                else:
                    img_path = await role_list_img(uid, True)

                    # 检查是否返回错误信息
                    if isinstance(img_path, str) and img_path.startswith("ERROR:"):
                        error_msg = img_path[6:]  # 移除 "ERROR:" 前缀
                        logger.error(f"角色列表生成失败 | UID: {uid} | 错误: {error_msg}")
                        yield event.plain_result(f"❌ {error_msg}")
                        return

                    logger.info(f"使用本地渲染图片生成成功 | {img_path}")
                    yield event.image_result(img_path)

            except ValueError as e:
                # logger.error(f"❌ Enka.network似乎不稳定或在维护中，再试一次或稍后再试。错误：{str(e)}", exc_info=True)
                # yield event.plain_result(f"❌ Enka.network似乎不稳定或在维护中，再试一次或稍后再试。错误：{str(e)}")
                logger.error(f"生成失败 | UID: {uid} | 错误: {str(e)}", exc_info=True)
                yield event.plain_result(f"❌ {str(e)}")

            except Exception as e:
                # 捕获其他未知错误
                err_msg = ""
                if "424" in str(e):
                    err_msg += "\nEnka.network似乎不稳定或在维护中，再试一次或稍后再试"
                logger.error(f"角色列表生成失败 | UID: {uid} | 错误: {str(e)}{err_msg}", exc_info=True)
                yield event.plain_result(f"❌ 生成角色列表时发生错误: {str(e)}{err_msg}")
        else:
            # 转换 uid 为字符串
            uid_str = str(uid)

            yield event.plain_result(f"正在生成 UID {uid_str} 的角色 {character_index} 卡片...")

            if self.enable_local_card:
                # 调用本地 enkacard 生成
                image_path = await enka_card(uid_str, character_index)

                if isinstance(image_path, str) and image_path.startswith("ERROR:"):
                    error_msg = image_path[6:]
                    logger.error(f"角色卡片生成失败 | UID: {uid_str} | 错误: {error_msg}")
                    yield event.plain_result(f"❌ {error_msg}")
                    return

                yield event.image_result(image_path)
            else:
                # 调用阿里云函数生成
                try:
                    roles = await list_roles_dict(uid_str)
                except ValueError as e:
                    logger.error(f"获取角色列表失败 | UID: {uid_str} | 错误: {str(e)}")
                    yield event.plain_result(f"❌ 获取角色列表失败: {str(e)}")
                    return

                if not roles or character_index < 1 or character_index > len(roles):
                    yield event.plain_result(
                        f"❌ 角色编号无效，请在 1-{len(roles)} 范围内选择"
                    )
                    return

                avatar_id = str(roles[character_index - 1]["id"])

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            ENKA_CARD_API_URL,
                            json={"uid": uid_str, "avatar_id": avatar_id},
                            timeout=aiohttp.ClientTimeout(total=60),
                        ) as resp:
                            if resp.status != 200:
                                err = f"云端服务返回 HTTP {resp.status}"
                                logger.error(f"云端卡片生成失败 | UID: {uid_str} | {err}")
                                yield event.plain_result(f"❌ {err}")
                                return
                            data = await resp.json()
                except Exception as e:
                    logger.error(
                        f"云端卡片生成请求异常 | UID: {uid_str} | 错误: {str(e)}",
                        exc_info=True,
                    )
                    yield event.plain_result(f"❌ 云端卡片生成请求异常: {str(e)}")
                    return

                if not data.get("success"):
                    err = data.get("error") or data.get("message") or "未知错误"
                    logger.error(f"云端卡片生成失败 | UID: {uid_str} | 错误: {err}")
                    yield event.plain_result(f"❌ 云端卡片生成失败: {err}")
                    return

                image_url = data.get("url")
                if not image_url:
                    yield event.plain_result("❌ 云端返回结果中缺少图片链接")
                    return

                logger.info(f"使用云端生成卡片成功 | UID: {uid_str} | URL: {image_url}")
                yield event.image_result(image_url)


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        pass
