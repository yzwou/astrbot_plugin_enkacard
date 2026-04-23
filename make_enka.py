import aiohttp

idAvatarMap = {
    10000001: '凯特',
    10000002: '神里绫华',
    10000003: '琴',
    10000005: '主角',
    10000006: '丽莎',
    10000007: '主角',
    10000014: '芭芭拉',
    10000015: '凯亚',
    10000016: '迪卢克',
    10000020: '雷泽',
    10000021: '安柏',
    10000022: '温迪',
    10000023: '香菱',
    10000024: '北斗',
    10000025: '行秋',
    10000026: '魈',
    10000027: '凝光',
    10000029: '可莉',
    10000030: '钟离',
    10000031: '菲谢尔',
    10000032: '班尼特',
    10000033: '达达利亚',
    10000034: '诺艾尔',
    10000035: '七七',
    10000036: '重云',
    10000037: '甘雨',
    10000038: '阿贝多',
    10000039: '迪奥娜',
    10000041: '莫娜',
    10000042: '刻晴',
    10000043: '砂糖',
    10000044: '辛焱',
    10000045: '罗莎莉亚',
    10000046: '胡桃',
    10000047: '枫原万叶',
    10000048: '烟绯',
    10000049: '宵宫',
    10000050: '托马',
    10000051: '优菈',
    10000052: '雷电将军',
    10000053: '早柚',
    10000054: '珊瑚宫心海',
    10000055: '五郎',
    10000056: '九条裟罗',
    10000057: '荒泷一斗',
    10000058: '八重神子',
    10000059: '鹿野院平藏',
    10000060: '夜兰',
    10000062: '埃洛伊',
    10000063: '申鹤',
    10000064: '云堇',
    10000065: '久岐忍',
    10000066: '神里绫人',
    10000067: '柯莱',
    10000068: '多莉',
    10000069: '提纳里',
    10000070: '妮露',
    10000071: '赛诺',
    10000072: '坎蒂丝',
    10000073: '纳西妲',
    10000075: '流浪者',
    10000078: '艾尔海森',
    10000079: '迪希雅',
    10000082: '白术',
    10000084: '林尼',
    10000086: '莱欧斯利',
    10000087: '那维莱特',
    10000089: '芙宁娜',
    10000091: '娜维娅',
    10000093: '闲云',
    10000094: '千织',
    10000095: '希格雯',
    10000096: '阿蕾奇诺',
    10000098: '克洛琳德',
    10000099: '艾梅莉埃',
    10000101: '基尼奇',
    10000102: '玛拉妮',
    10000103: '希诺宁',
    10000104: '恰斯卡',
    10000106: '玛薇卡',
    10000107: '茜特菈莉',
    10000109: '梦见月瑞希',
    10000111: '瓦蕾莎',
    10000112: '爱可菲',
    10000114: '丝柯克',
    10000116: '伊涅芙',
    10000119: '菈乌玛',
    10000120: '菲林斯',
    10000123: '杜林'
}
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

