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

async def enka_card(uid="269377658", idx = "10000047"):
    """
    生成单角色卡片图片

    :param uid: 玩家UID
    :param avatar_id: 角色ID
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

    avatar_id = list_roles_dict("269377658")[int(idx)-1]

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