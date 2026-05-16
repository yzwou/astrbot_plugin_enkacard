import sys
import os
# 添加当前插件目录到Python路径，确保导入正确的enkacard模块
# plugin_dir = os.path.dirname(os.path.abspath(__file__))
# if plugin_dir not in sys.path:
#     sys.path.insert(0, plugin_dir)

from enkacard import encbanner
import asyncio

pick = {
    "size": True,
    "get_characters": True,
    "add_characters": True,
    "add_generate": True,
    "get_generate": True
}


async def update():
    await encbanner.update()

async def test():
    async with encbanner.ENC(uid = "269377658", lang="chs", character_id="10000047") as encard:
        return await encard.creat()

async def card(uid = "269377658", avatar_id = "10000047"):
    async with encbanner.ENC(uid=uid, character_id=str(avatar_id), lang="chs", pickle = pick) as encard:
        c = await encard.creat()
        for d in c.card:
            filename = f"{uid}_{d.id}.png"
            d.card.save(filename)
            return filename

        return "None"


result = asyncio.run(card())

print(result)
# asyncio.run(main())