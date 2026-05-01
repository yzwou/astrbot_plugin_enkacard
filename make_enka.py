import aiohttp

import json
import os

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_pkg_dir, "avatar_names.json"), "r", encoding="utf-8") as _f:
    idAvatarMap = {int(k): v for k, v in json.load(_f).items()}
idEnergyMap = {
    1: "火",
    2: "水",
    3: "草",
    4: "雷",
    5: "冰",
    6: "岩",
    7: "风"
}
status_codes = {
    400: "UID格式错误",
    404: "玩家不存在",
    424: "游戏维护中",
    429: "请求频率限制",
    500: "服务器错误",
    503: "出现了莫名奇妙的错误"
}
pick = {
    "size": True,
    "get_characters": True,
    "add_characters": True,
    "add_generate": True,
    "get_generate": True
}


async def fetch_json(uid):
    url = f"https://enka.network/api/uid/{uid}"  # 替换为你的真实 API 地址
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                elif resp.status == 400:
                    return {"error": "UID似乎不正确", "status": 400}
                else:
                    return {"error": f"API请求失败: {resp.status}", "status": resp.status}
    except Exception as e:
        return {"error": f"请求异常: {str(e)}", "status": -1}


async def list_roles(uid):
    data = await fetch_json(uid)
    
    # 检查是否返回错误信息
    if "error" in data:
        return f"查询失败: {data['error']}"
    
    info_list = data.get("playerInfo", {}).get("showAvatarInfoList", [])
    s = "\n"
    id_list = []
    for i, x in enumerate(info_list):
        name = idAvatarMap.get(x["avatarId"], f"未知{x['avatarId']}")
        lvl = x.get("level")
        elem = idEnergyMap.get(x.get("energyType"), "未知")
        id_list.append(x["avatarId"])
        s += f"{i+1}. {name} 元素：{elem} 等级：{lvl}\n"
    return s


async def list_roles_dict(uid):
    data = await fetch_json(uid)
    
    # 检查是否返回错误信息
    if "error" in data:
        raise ValueError(data['error'])
    info_list = data.get("playerInfo", {}).get("showAvatarInfoList", [])
    character_list = []
    for i, x in enumerate(info_list):
        name = idAvatarMap.get(x["avatarId"], f"未知{x['avatarId']}")
        lvl = x.get("level")
        elem = idEnergyMap.get(x.get("energyType"), "未知")
        character_dict = {"id": x["avatarId"], "name": name, "ele": elem, "lvl": lvl}
        character_list.append(character_dict)
    return character_list


async def get_uid_info(uid):
    data = await fetch_json(uid)

    # 检查是否返回错误信息
    if "error" in data:
        return f"查询失败: {data['error']}"

    if "playerInfo" not in data:
        return "查询失败，可能是 UID 不存在或未公开。"

    info = data.get("playerInfo")
    name = info.get("nickname", "None")
    level = info.get("level", "None")
    world_level = info.get("worldLevel", "None")
    floor = info.get("towerFloorIndex", None)
    chamber = info.get("towerLevelIndex", None)
    star = info.get("towerStarIndex", None)

    if floor is None:
        abyss_str = "无记录"
    else:
        abyss_str = f"{floor}-{chamber} {star}★"

    act = info.get("theaterActIndex", None)
    star2 = info.get("theaterStarIndex", None)

    if act is None:
        theater_str = "无记录"
    else:
        theater_str = f"{act}|{star2}"

    return (
        f"\n{name}\n"
        f"UID：{uid}\n"
        f"冒险等级：{level}  世界等级：{world_level}\n"
        f"深境螺旋：{abyss_str}\n"
        f"幻想真境剧诗：{theater_str}"
    )

if __name__ == "__main__":
    import asyncio
    async def main():
        a = await list_roles_dict("269377658")
        print(a)
    asyncio.run(main())

