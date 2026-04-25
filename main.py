import asyncio
import os

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .ysenka_spider import async_scrape_enka
from .generate_role_list import role_list_img


@register("astrbot_plugin_enkacard", "yzwou", "获取指定原神玩家信息的插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.enable_local = self.config.get("enable_local", False)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    @filter.command("角色")
    async def character_card(self, event: AstrMessageEvent, uid: str = None, character_index: int = None):
        """获取原神角色卡片图片。用法: /角色 [uid] [角色编号（选填）]"""
        if not uid:
            yield event.plain_result("用法: /角色 [uid] [角色编号（选填）]\n示例: /角色 269377658 1")
            return

        if character_index is None:
            # try:
            if not self.enable_local:
                html_file_path = await role_list_img(uid, False)
                options = {
                    "type": "jpeg",
                    "quality": 100
                }
                with open(html_file_path, 'r', encoding='utf-8') as f:
                    TMPL = f.read()
                url = await self.html_render(TMPL, {"items": ["吃饭", "睡觉", "玩原神"]}, options=options) # 第二个参数是 Jinja2 的渲染数据

                logger.info(f"使用API渲染图片生成成功 | {url}")
                yield event.image_result(url)
            else:
                img_path = await role_list_img(uid, True)
                logger.info(f"使用本地渲染图片生成成功 | {img_path}")
                yield event.image_result(img_path)

            # except ValueError as e:
            #     # logger.error(f"❌ Enka.network似乎不稳定或在维护中，再试一次或稍后再试。错误：{str(e)}", exc_info=True)
            #     # yield event.plain_result(f"❌ Enka.network似乎不稳定或在维护中，再试一次或稍后再试。错误：{str(e)}")
            #     logger.error(f"生成失败 | UID: {uid} | 错误: {str(e)}", exc_info=True)
            #     yield event.plain_result(f"❌ {str(e)}")
            #
            # except Exception as e:
            #     # 捕获其他未知错误
            #     err_msg = ""
            #     if "424" in str(e):
            #         err_msg += "\nEnka.network似乎不稳定或在维护中，再试一次或稍后再试"
            #     logger.error(f"角色列表生成失败 | UID: {uid} | 错误: {str(e)}{err_msg}", exc_info=True)
            #     yield event.plain_result(f"❌ 生成角色列表时发生错误: {str(e)}{err_msg}")

                # 转换 uid 为字符串
                uid_str = str(uid)

                yield event.plain_result(f"正在生成 UID {uid_str} 的角色卡片...")

                # 调用爬虫函数，返回值为 (success, result, error)
                success, image_path, error = await async_scrape_enka(uid_str, character_index=character_index, headless=True)

                if not success:
                    # 记录详细错误信息到日志
                    logger.error(f"角色卡片生成失败 | UID: {uid_str} | 错误: {error}")
                    yield event.plain_result(f"❌ 角色卡片生成失败: {error}")
                    return

                # 发送图片（使用 image_result 发送本地图片）
                yield event.image_result(image_path)

    @filter.command("image") # 注册一个 /image 指令，接收 text 参数。
    async def on_aiocqhttp(self, event: AstrMessageEvent, text: str):
        url = await self.text_to_image(text) # text_to_image() 是 Star 类的一个方法。
        # path = await self.text_to_image(text, return_url = False) # 如果你想保存图片到本地
        yield event.image_result(url)


    @filter.command("todo")
    async def custom_t2i_tmpl(self, event: AstrMessageEvent):
        options = {
            "quality": 90,
            "full_page": False,
        } # 可选择传入渲染选项。
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python_characters.html")
        with open(html_path, 'r', encoding='utf-8') as f:
            TMPL = f.read()
        url = await self.html_render(TMPL, {"items": ["吃饭", "睡觉", "玩原神"]}, options=options) # 第二个参数是 Jinja2 的渲染数据
        yield event.image_result(url)


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        pass
