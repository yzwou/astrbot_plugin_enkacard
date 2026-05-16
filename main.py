import asyncio
import os
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


from .ysenka import *
from .generate_role_list import role_list_img

PLUGIN_NAME = "astrbot_plugin_enkacard"


@register("astrbot_plugin_enkacard", "yzwou", "获取指定原神玩家信息的插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.enable_local = self.config.get("enable_local", False)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        plugin_data_path = Path(get_astrbot_data_path()) / "plugin_data" / PLUGIN_NAME
        plugin_data_path.mkdir(parents=True, exist_ok=True)

        first_run_flag = plugin_data_path / ".initialized"
        if not first_run_flag.exists():
            await self._on_first_run(plugin_data_path)

    async def _on_first_run(self, plugin_data_path: Path):
        """插件首次运行时执行，仅调用一次。"""
        logger.info(f"{PLUGIN_NAME} 首次运行，执行初始化...")
        try:
            await enka_update()
        except Exception as e:
            logger.error(f"初始化失败：{e}")
            return
        logger.info(f"{PLUGIN_NAME} 初始化完成")
        (plugin_data_path / ".initialized").touch()


    @filter.command("ys")
    async def character_card(self, event: AstrMessageEvent, uid: str = None, character_index: int = None):
        """获取原神角色卡片图片。用法: /ys [uid] [角色编号（选填）]"""
        if not uid:
            yield event.plain_result("用法: /ys [uid] [角色编号（选填）]\n示例: /ys 269377658 1")
            return

        if character_index is None:
            try:
                if not self.enable_local:
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

            # 调用爬虫函数，返回值为 (success, result, error)
            success, image_path, error = await ysenka.enka_card(uid_str, character_index, plugin_data_path =Path(get_astrbot_data_path()) / "plugin_data" / PLUGIN_NAME)

            if not success:
                # 记录详细错误信息到日志
                logger.error(f"角色卡片生成失败 | UID: {uid_str} | 错误: {error}")
                yield event.plain_result(f"❌ 角色卡片生成失败: {error}")
                return

            # 发送图片（使用 image_result 发送本地图片）
            yield event.image_result(image_path)


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        pass
