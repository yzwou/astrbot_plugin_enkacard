import asyncio
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import aiohttp
from enkanetwork import Assets
from enkanetwork.assets import PATH as ENKANETWORK_PACKAGE_PATH
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api import FunctionTool, logger
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext

from ..make_enka import idAvatarMap, idEnergyMap
from ..ysenka import (
    get_character_catalog,
    resolve_character_alias_with_llm,
    resolve_character_avatar_ids,
)

ENKA_API_URL = "https://enka.network/api/uid/{uid}"
USER_AGENT = "astrbot_plugin_enkacard/1.0.0 (genshin_character_info)"
REQUEST_TIMEOUT_SECONDS = 20

_UID_RE = re.compile(r"^[1256789]\d{8,9}$")
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_INFLIGHT: dict[str, asyncio.Task] = {}
_CACHE_LOCK = asyncio.Lock()
_ASSET_MTIME_NS: int | None = None

_HTTP_ERRORS = {
    400: ("invalid_uid", "UID 格式错误"),
    404: ("player_not_found", "未找到该 UID 对应的玩家"),
    424: ("game_maintenance", "游戏数据维护中，请稍后重试"),
    429: ("rate_limited", "Enka.Network 请求过于频繁，请稍后重试"),
    500: ("enka_server_error", "Enka.Network 服务器错误"),
    503: ("enka_unavailable", "Enka.Network 服务暂时不可用"),
}

_ELEMENT_NAMES = {
    "Fire": "火",
    "Water": "水",
    "Grass": "草",
    "Electric": "雷",
    "Ice": "冰",
    "Rock": "岩",
    "Wind": "风",
}

_QUALITY_RARITY = {
    "QUALITY_ORANGE": 5,
    "QUALITY_PURPLE": 4,
    "QUALITY_BLUE": 3,
    "QUALITY_GREEN": 2,
}

_ARTIFACT_SLOT_NAMES = {
    "EQUIP_BRACER": "生之花",
    "EQUIP_NECKLACE": "死之羽",
    "EQUIP_SHOES": "时之沙",
    "EQUIP_RING": "空之杯",
    "EQUIP_DRESS": "理之冠",
}

_PROP_NAMES = {
    "FIGHT_PROP_BASE_ATTACK": "基础攻击力",
    "FIGHT_PROP_HP": "生命值",
    "FIGHT_PROP_ATTACK": "攻击力",
    "FIGHT_PROP_DEFENSE": "防御力",
    "FIGHT_PROP_HP_PERCENT": "生命值",
    "FIGHT_PROP_ATTACK_PERCENT": "攻击力",
    "FIGHT_PROP_DEFENSE_PERCENT": "防御力",
    "FIGHT_PROP_CRITICAL": "暴击率",
    "FIGHT_PROP_CRITICAL_HURT": "暴击伤害",
    "FIGHT_PROP_CHARGE_EFFICIENCY": "元素充能效率",
    "FIGHT_PROP_HEAL_ADD": "治疗加成",
    "FIGHT_PROP_ELEMENT_MASTERY": "元素精通",
    "FIGHT_PROP_PHYSICAL_ADD_HURT": "物理伤害加成",
    "FIGHT_PROP_FIRE_ADD_HURT": "火元素伤害加成",
    "FIGHT_PROP_ELEC_ADD_HURT": "雷元素伤害加成",
    "FIGHT_PROP_WATER_ADD_HURT": "水元素伤害加成",
    "FIGHT_PROP_WIND_ADD_HURT": "风元素伤害加成",
    "FIGHT_PROP_ICE_ADD_HURT": "冰元素伤害加成",
    "FIGHT_PROP_ROCK_ADD_HURT": "岩元素伤害加成",
    "FIGHT_PROP_GRASS_ADD_HURT": "草元素伤害加成",
}

_PERCENT_PROP_IDS = {
    "FIGHT_PROP_HP_PERCENT",
    "FIGHT_PROP_ATTACK_PERCENT",
    "FIGHT_PROP_DEFENSE_PERCENT",
    "FIGHT_PROP_CRITICAL",
    "FIGHT_PROP_CRITICAL_HURT",
    "FIGHT_PROP_CHARGE_EFFICIENCY",
    "FIGHT_PROP_HEAL_ADD",
    "FIGHT_PROP_PHYSICAL_ADD_HURT",
    "FIGHT_PROP_FIRE_ADD_HURT",
    "FIGHT_PROP_ELEC_ADD_HURT",
    "FIGHT_PROP_WATER_ADD_HURT",
    "FIGHT_PROP_WIND_ADD_HURT",
    "FIGHT_PROP_ICE_ADD_HURT",
    "FIGHT_PROP_ROCK_ADD_HURT",
    "FIGHT_PROP_GRASS_ADD_HURT",
}


class EnkaAPIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )


def _query_payload(character: str | None) -> dict[str, Any]:
    single = character not in (None, "")
    return {
        "mode": "single" if single else "all",
        "input_character": str(character).strip() if single else None,
        "resolved_avatar_id": None,
    }


def _error_result(
    uid: str,
    character: str | None,
    code: str,
    message: str,
    http_status: int | None = None,
) -> str:
    return _json_dumps(
        {
            "schema_version": 1,
            "ok": False,
            "uid": str(uid).strip() if uid is not None else "",
            "query": _query_payload(character),
            "error": {
                "code": code,
                "message": message,
                "http_status": http_status,
            },
        }
    )


def _positive_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


async def _request_enka(uid: str) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    headers = {"User-Agent": USER_AGENT}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(ENKA_API_URL.format(uid=uid)) as response:
                if response.status != 200:
                    code, message = _HTTP_ERRORS.get(
                        response.status,
                        ("enka_http_error", f"Enka.Network 返回 HTTP {response.status}"),
                    )
                    raise EnkaAPIError(code, message, response.status)
                try:
                    data = await response.json(content_type=None)
                except (json.JSONDecodeError, aiohttp.ContentTypeError) as exc:
                    raise EnkaAPIError(
                        "invalid_api_response",
                        "Enka.Network 返回了无法解析的数据",
                        response.status,
                    ) from exc
    except EnkaAPIError:
        raise
    except asyncio.TimeoutError as exc:
        raise EnkaAPIError("request_timeout", "请求 Enka.Network 超时") from exc
    except aiohttp.ClientError as exc:
        raise EnkaAPIError(
            "network_error",
            f"请求 Enka.Network 失败：{str(exc)}",
        ) from exc
    except OSError as exc:
        raise EnkaAPIError(
            "network_error",
            f"请求 Enka.Network 失败：{str(exc)}",
        ) from exc

    if not isinstance(data, dict):
        raise EnkaAPIError("invalid_api_response", "Enka.Network 返回的数据格式无效")
    return data


async def _request_and_cache(uid: str) -> dict[str, Any]:
    try:
        data = await _request_enka(uid)
        ttl = _positive_int(data.get("ttl"))
        if ttl > 0:
            async with _CACHE_LOCK:
                _CACHE[uid] = (time.monotonic() + ttl, data)
        return data
    finally:
        async with _CACHE_LOCK:
            current_task = asyncio.current_task()
            if _INFLIGHT.get(uid) is current_task:
                _INFLIGHT.pop(uid, None)


async def fetch_enka_data(uid: str) -> tuple[dict[str, Any], bool]:
    """获取 UID 数据，遵循 Enka ttl 缓存并合并并发中的相同请求。"""
    now = time.monotonic()
    async with _CACHE_LOCK:
        cached = _CACHE.get(uid)
        if cached is not None:
            expires_at, data = cached
            if expires_at > now:
                return data, True
            _CACHE.pop(uid, None)

        task = _INFLIGHT.get(uid)
        shared_request = task is not None
        if task is None:
            task = asyncio.create_task(_request_and_cache(uid))
            _INFLIGHT[uid] = task

    data = await asyncio.shield(task)
    return data, shared_request


def _local_assets_mtime_ns() -> int | None:
    try:
        return max(
            path.stat().st_mtime_ns
            for path in (Path(ENKANETWORK_PACKAGE_PATH) / "assets").rglob("*.json")
        )
    except (OSError, ValueError):
        return None


def _reload_local_assets() -> None:
    global _ASSET_MTIME_NS

    current_mtime_ns = _local_assets_mtime_ns()
    if (
        Assets.DATA
        and Assets.HASH_MAP
        and str(Assets.LANGS).upper() == "CHS"
        and _ASSET_MTIME_NS == current_mtime_ns
    ):
        return
    try:
        Assets("chs")
        _ASSET_MTIME_NS = current_mtime_ns
    except Exception as exc:
        logger.warning(f"加载 Enka 中文资源失败，将使用 ID 回退：{str(exc)}")


def _lookup_hash(hash_id: Any, group: str | None = None) -> str | None:
    if hash_id in (None, ""):
        return None

    groups = [group] if group and group in Assets.HASH_MAP else list(Assets.HASH_MAP)
    for group_name in groups:
        entry = Assets.HASH_MAP.get(group_name, {}).get(str(hash_id))
        if not isinstance(entry, dict):
            continue
        value = entry.get("CHS") or entry.get("EN")
        if value:
            return str(value)
    return None


def _character_asset(avatar: dict[str, Any]) -> dict[str, Any] | None:
    avatar_id = _positive_int(avatar.get("avatarId"))
    asset_key = str(avatar_id)
    if avatar_id in (10000005, 10000007):
        asset_key = f"{avatar_id}-{avatar.get('skillDepotId', 0)}"
    data = Assets.DATA.get("characters", {}).get(asset_key)
    return data if isinstance(data, dict) else None


def _round_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _round_number(value: Any) -> int | float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    rounded = round(number, 1)
    return int(rounded) if rounded.is_integer() else rounded


def _ratio_to_percent(value: Any) -> int | float:
    try:
        return _round_number(float(value) * 100)
    except (TypeError, ValueError):
        return 0


def _equipment_stat(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    prop_id = data.get("mainPropId") or data.get("appendPropId")
    if not prop_id:
        return None
    prop_id = str(prop_id)
    return {
        "prop_id": prop_id,
        "name": _lookup_hash(prop_id, "fight_props") or _PROP_NAMES.get(prop_id),
        "value": _round_number(data.get("statValue")),
        "unit": "%" if prop_id in _PERCENT_PROP_IDS else None,
    }


def _format_weapon(
    raw_equipment: dict[str, Any],
) -> dict[str, Any]:
    flat = raw_equipment.get("flat") or {}
    weapon = raw_equipment.get("weapon") or {}
    weapon_stats = flat.get("weaponStats") or []
    refinement_values = list((weapon.get("affixMap") or {}).values())
    ascension = _positive_int(weapon.get("promoteLevel"))
    max_level = (ascension * 10) + (10 if ascension > 0 else 0) + 20

    secondary_stat = _equipment_stat(weapon_stats[1]) if len(weapon_stats) > 1 else None
    base_attack = 0
    if weapon_stats:
        base_attack = _round_int(weapon_stats[0].get("statValue"))

    return {
        "item_id": _positive_int(raw_equipment.get("itemId")),
        "name": _lookup_hash(flat.get("nameTextMapHash"), "weapons"),
        "rarity": _positive_int(flat.get("rankLevel")) or None,
        "level": _positive_int(weapon.get("level")),
        "max_level": max_level,
        "ascension": ascension,
        "refinement": (_positive_int(refinement_values[0]) + 1) if refinement_values else 1,
        "base_attack": base_attack,
        "secondary_stat": secondary_stat,
        "icon": flat.get("icon"),
    }


def _format_artifact(raw_equipment: dict[str, Any]) -> dict[str, Any]:
    flat = raw_equipment.get("flat") or {}
    reliquary = raw_equipment.get("reliquary") or {}
    return {
        "item_id": _positive_int(raw_equipment.get("itemId")),
        "name": _lookup_hash(flat.get("nameTextMapHash"), "artifacts"),
        "set_id": _positive_int(flat.get("setId")) or None,
        "set_name": _lookup_hash(flat.get("setNameTextMapHash"), "artifact_sets"),
        "slot": _ARTIFACT_SLOT_NAMES.get(flat.get("equipType"), flat.get("equipType")),
        "rarity": _positive_int(flat.get("rankLevel")) or None,
        "level": max(0, _positive_int(reliquary.get("level")) - 1),
        "main_stat": _equipment_stat(flat.get("reliquaryMainstat")),
        "sub_stats": [
            stat
            for stat in (
                _equipment_stat(item)
                for item in (flat.get("reliquarySubstats") or [])
            )
            if stat is not None
        ],
        "icon": flat.get("icon"),
    }


def _format_talents(
    avatar: dict[str, Any],
    character_asset: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    raw_levels = avatar.get("skillLevelMap") or {}
    extra_levels = avatar.get("proudSkillExtraLevelMap") or {}
    skill_ids = list((character_asset or {}).get("skills") or [])
    if not skill_ids:
        skill_ids = [_positive_int(skill_id) for skill_id in raw_levels]

    talents = []
    for skill_id in skill_ids:
        skill_data = Assets.DATA.get("skills", {}).get(str(skill_id)) or {}
        base_level = _positive_int(raw_levels.get(str(skill_id)))
        proud_group_id = skill_data.get("proudSkillGroupId")
        extra_level = _positive_int(extra_levels.get(str(proud_group_id)))
        talents.append(
            {
                "skill_id": _positive_int(skill_id),
                "name": _lookup_hash(skill_data.get("nameTextMapHash"), "skills"),
                "level": base_level + extra_level,
                "boosted_by_constellation": extra_level > 0,
            }
        )
    return talents


def _format_constellations(avatar: dict[str, Any]) -> dict[str, Any]:
    unlocked_ids = avatar.get("talentIdList") or []
    unlocked = []
    for constellation_id in unlocked_ids:
        constellation_data = Assets.DATA.get("constellations", {}).get(
            str(constellation_id),
            {},
        )
        unlocked.append(
            {
                "constellation_id": _positive_int(constellation_id),
                "name": _lookup_hash(
                    constellation_data.get("nameTextMapHash"),
                    "constellations",
                ),
            }
        )
    return {"level": len(unlocked_ids), "unlocked": unlocked}


def _format_stats(avatar: dict[str, Any]) -> dict[str, Any]:
    stats = avatar.get("fightPropMap") or {}
    return {
        "max_hp": _round_int(stats.get("2000")),
        "attack": _round_int(stats.get("2001")),
        "defense": _round_int(stats.get("2002")),
        "elemental_mastery": _round_int(stats.get("28")),
        "crit_rate_percent": _ratio_to_percent(stats.get("20")),
        "crit_damage_percent": _ratio_to_percent(stats.get("22")),
        "energy_recharge_percent": _ratio_to_percent(stats.get("23")),
        "healing_bonus_percent": _ratio_to_percent(stats.get("26")),
        "damage_bonus_percent": {
            "all": _ratio_to_percent(stats.get("24")),
            "physical": _ratio_to_percent(stats.get("30")),
            "pyro": _ratio_to_percent(stats.get("40")),
            "electro": _ratio_to_percent(stats.get("41")),
            "hydro": _ratio_to_percent(stats.get("42")),
            "dendro": _ratio_to_percent(stats.get("43")),
            "anemo": _ratio_to_percent(stats.get("44")),
            "geo": _ratio_to_percent(stats.get("45")),
            "cryo": _ratio_to_percent(stats.get("46")),
        },
    }


def _format_character(
    avatar: dict[str, Any],
    preview: dict[str, Any] | None,
) -> dict[str, Any]:
    avatar_id = _positive_int(avatar.get("avatarId"))
    character_asset = _character_asset(avatar)
    prop_map = avatar.get("propMap") or {}
    ascension = _positive_int((prop_map.get("1002") or {}).get("ival"))
    level = _positive_int(
        (prop_map.get("4001") or {}).get("val")
        or (prop_map.get("4001") or {}).get("ival")
    )
    max_level = (ascension * 10) + (10 if ascension > 0 else 0) + 20

    name = None
    rarity = None
    element = None
    if character_asset:
        name = _lookup_hash(character_asset.get("nameTextMapHash"), "characters")
        rarity = _QUALITY_RARITY.get(character_asset.get("qualityType"))
        element = _ELEMENT_NAMES.get(character_asset.get("costElemType"))
    name = name or idAvatarMap.get(avatar_id)
    if element is None and preview:
        element = idEnergyMap.get(preview.get("energyType"))

    weapon = None
    artifacts = []
    for equipment in avatar.get("equipList") or []:
        if "weapon" in equipment:
            weapon = _format_weapon(equipment)
        elif "reliquary" in equipment:
            artifacts.append(_format_artifact(equipment))

    set_counts = Counter(
        (artifact.get("set_id"), artifact.get("set_name"))
        for artifact in artifacts
    )
    artifact_sets = [
        {"set_id": set_id, "name": set_name, "pieces": pieces}
        for (set_id, set_name), pieces in sorted(
            set_counts.items(),
            key=lambda item: (-item[1], item[0][0] or 0),
        )
    ]

    return {
        "avatar_id": avatar_id,
        "name": name,
        "element": element,
        "rarity": rarity,
        "level": level,
        "max_level": max_level,
        "ascension": ascension,
        "friendship_level": _positive_int(
            (avatar.get("fetterInfo") or {}).get("expLevel")
        ),
        "constellations": _format_constellations(avatar),
        "talents": _format_talents(avatar, character_asset),
        "stats": _format_stats(avatar),
        "weapon": weapon,
        "artifact_sets": artifact_sets,
        "artifacts": artifacts,
    }


def format_characters(
    data: dict[str, Any],
    selected_avatar_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    _reload_local_assets()
    player_info = data.get("playerInfo") or {}
    preview_by_id = {
        _positive_int(preview.get("avatarId")): preview
        for preview in (player_info.get("showAvatarInfoList") or [])
    }
    characters = []
    for avatar in data.get("avatarInfoList") or []:
        avatar_id = _positive_int(avatar.get("avatarId"))
        if selected_avatar_ids is not None and avatar_id not in selected_avatar_ids:
            continue
        characters.append(_format_character(avatar, preview_by_id.get(avatar_id)))
    return characters


@dataclass
class getinfo(FunctionTool):
    enable_llm_character_alias: bool = True
    name: str = "genshin_character_info"
    description: str = (
        "当AI需要了解原神玩家单个或全部角色的详细配装信息时调用，返回 JSON；"
        "character 可传完整中文名、简称或 8 位 avatarId；不传时返回全部公开角色。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "9 至 10 位原神玩家 UID",
                },
                "character": {
                    "type": "string",
                    "description": "角色完整中文名、简称或 8 位 avatarId；省略则返回全部角色",
                },
            },
            "required": ["uid"],
        }
    )

    async def call(
        self,
        context: ContextWrapper[AstrAgentContext],
        uid: str = "",
        character: str | None = None,
    ) -> str:
        uid_text = str(uid).strip()
        if not _UID_RE.fullmatch(uid_text):
            return _error_result(
                uid_text,
                character,
                "invalid_uid",
                "UID 必须是以有效区服数字开头的 9 至 10 位数字",
                400,
            )

        requested_character = None
        if character not in (None, ""):
            normalized_character = str(character).strip()
            if normalized_character:
                requested_character = normalized_character

        selected_avatar_ids = None
        if requested_character is not None:
            astr_context = None
            event = None
            try:
                astr_context = context.context.context
                event = context.context.event
            except AttributeError:
                pass

            async def llm_alias_resolver(selector_text, roles):
                if (
                    not self.enable_llm_character_alias
                    or astr_context is None
                    or event is None
                ):
                    return None
                return await resolve_character_alias_with_llm(
                    astr_context,
                    event,
                    selector_text,
                    roles,
                )

            try:
                selected_avatar_ids = await resolve_character_avatar_ids(
                    requested_character,
                    alias_resolver=llm_alias_resolver,
                    llm_roles=get_character_catalog(),
                )
            except ValueError as exc:
                return _error_result(
                    uid_text,
                    requested_character,
                    "character_unrecognized",
                    str(exc),
                )

        try:
            data, cache_hit = await fetch_enka_data(uid_text)
        except EnkaAPIError as exc:
            return _error_result(
                uid_text,
                requested_character,
                exc.code,
                exc.message,
                exc.http_status,
            )
        except Exception as exc:
            logger.error(
                f"获取原神角色信息时发生未知错误 | UID: {uid_text} | 错误: {str(exc)}",
                exc_info=True,
            )
            return _error_result(
                uid_text,
                requested_character,
                "internal_error",
                "处理角色信息时发生内部错误",
            )

        raw_characters = data.get("avatarInfoList")
        if not isinstance(raw_characters, list) or not raw_characters:
            return _error_result(
                uid_text,
                requested_character,
                "showcase_unavailable",
                "该玩家未公开角色展柜，或展柜中没有详细角色数据",
            )

        matching_ids = {
            _positive_int(avatar.get("avatarId"))
            for avatar in raw_characters
            if selected_avatar_ids is None
            or _positive_int(avatar.get("avatarId")) in selected_avatar_ids
        }
        if selected_avatar_ids is not None and not matching_ids:
            return _error_result(
                uid_text,
                requested_character,
                "character_not_showcased",
                f"UID {uid_text} 的公开展柜中没有该角色",
            )
        if selected_avatar_ids is not None and len(matching_ids) > 1:
            return _error_result(
                uid_text,
                requested_character,
                "character_ambiguous",
                "角色名称对应多个公开角色，请改用 8 位 avatarId",
            )

        try:
            characters = format_characters(data, matching_ids if selected_avatar_ids else None)
        except Exception as exc:
            logger.error(
                f"格式化原神角色信息失败 | UID: {uid_text} | 错误: {str(exc)}",
                exc_info=True,
            )
            return _error_result(
                uid_text,
                requested_character,
                "format_error",
                "角色数据格式化失败",
            )

        player_info = data.get("playerInfo") or {}
        query = _query_payload(requested_character)
        if selected_avatar_ids is not None:
            query["resolved_avatar_id"] = next(iter(matching_ids))

        return _json_dumps(
            {
                "schema_version": 1,
                "ok": True,
                "uid": str(data.get("uid") or uid_text),
                "query": query,
                "player": {
                    "nickname": player_info.get("nickname"),
                    "signature": player_info.get("signature"),
                    "adventure_rank": player_info.get("level"),
                    "world_level": player_info.get("worldLevel"),
                    "public_character_count": len(raw_characters),
                },
                "characters": characters,
                "meta": {
                    "region": data.get("region"),
                    "returned_character_count": len(characters),
                    "enka_ttl_seconds": _positive_int(data.get("ttl")),
                    "cache_hit": cache_hit,
                },
            }
        )
