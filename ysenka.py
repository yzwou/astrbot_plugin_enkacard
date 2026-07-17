import sys
import os
import logging
import time
# 添加当前插件目录到Python路径，确保导入正确的enkacard模块
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from enkacard import encbanner
from .make_enka import *
import asyncio

from astrbot.api import logger
from pathlib import Path
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

PLUGIN_NAME = "astrbot_plugin_enkacard"

idEnergyMap = { 1: "火", 2: "水", 3: "草", 4: "雷", 5: "冰", 6: "岩", 7: "风" }

pick = {
    "size": True,
    "get_characters": True,
    "add_characters": True,
    "add_generate": True,
    "get_generate": True
}


async def enka_update():
    await encbanner.update()

async def enka_test():
    async with encbanner.ENC(uid = "269377658", lang="chs", character_id="10000047") as encard:
        return await encard.creat()

async def resolve_character(uid, selector):
    """根据角色列表序号或角色名解析 UID 当前展示的角色。"""
    roles = await list_roles_dict(str(uid))
    if not roles:
        raise ValueError(f"UID {uid} 没有公开展示角色")

    selector_text = str(selector).strip()
    if not selector_text:
        raise ValueError("角色序号或角色名不能为空")

    if selector_text.isdecimal():
        character_index = int(selector_text)
        if character_index < 1 or character_index > len(roles):
            raise ValueError(f"角色编号无效，请在 1-{len(roles)} 范围内选择")
        return character_index, roles[character_index - 1]

    # avatar_names.json 里可能有同名角色（例如不同元素的旅行者），
    # 因此先得到全部匹配 ID，再到该 UID 的实际展示列表中查找。
    matched_avatar_ids = {
        avatar_id for avatar_id, name in idAvatarMap.items()
        if name == selector_text
    }
    if not matched_avatar_ids:
        raise ValueError(f"未找到角色“{selector_text}”，请检查角色名是否正确")

    for character_index, role in enumerate(roles, start=1):
        if int(role["id"]) in matched_avatar_ids:
            return character_index, role

    raise ValueError(f"UID {uid} 的公开展示角色中没有“{selector_text}”")


async def enka_card(uid="269377658", idx="1", avatar_id=None):
    """
    生成单角色卡片图片

    :param uid: 玩家UID
    :param idx: 角色列表序号或角色名
    :param avatar_id: 已解析的角色 ID；传入时不再重复请求角色列表
    :return: 成功时返回图片绝对路径字符串，失败时返回错误信息字符串（以"ERROR:"开头）
    """
    try:
        plugin_data_path = Path(get_astrbot_data_path()) / "plugin_data" / PLUGIN_NAME
        plugin_data_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        error_msg = f"创建插件数据目录失败: {str(e)}"
        logger.error(error_msg)
        return f"ERROR:{error_msg}"

    max_retries = 3
    retry_delay = 2  # 秒
    last_error = None

    if avatar_id is None:
        try:
            _, role = await resolve_character(uid, idx)
            avatar_id = role["id"]
        except ValueError as e:
            return f"ERROR:{str(e)}"

    for attempt in range(1, max_retries + 1):
        try:
            async with encbanner.ENC(uid=uid, character_id=str(avatar_id), lang="chs", pickle=pick) as encard:
                c = await encard.creat()
                for d in c.card:
                    filename = plugin_data_path / f"{uid}_{d.id}.png"
                    d.card.save(str(filename))
                    return str(filename)

                error_msg = f"未生成任何角色卡片 (uid={uid}, avatar_id={avatar_id})"
                logger.error(error_msg)
                return f"ERROR:{error_msg}"
        except Exception as e:
            last_error = e
            err_str = str(e)
            is_timeout = "Timeout" in err_str or "timeout" in err_str or "enka.network" in err_str

            if is_timeout and attempt < max_retries:
                logger.warning(
                    f"enka.network 请求超时，正在重试 ({attempt}/{max_retries})... 错误: {err_str}"
                )
                await asyncio.sleep(retry_delay)
                continue

            error_msg = f"生成角色卡片失败 (已尝试 {attempt} 次): {err_str}"
            logger.error(error_msg)
            return f"ERROR:{error_msg}"

    # 理论上不会走到这里，兜底
    error_msg = f"生成角色卡片失败 (已重试 {max_retries} 次): {str(last_error)}"
    logger.error(error_msg)
    return f"ERROR:{error_msg}"

if __name__ == "__main__":
    result = asyncio.run(enka_card())
    print(result)

# asyncio.run(main())
