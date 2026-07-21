# Changelog

## 2026-07-21

- 明确区分 `genshin_card` 与 `genshin_character_info` 的调用场景。
- “看一下/查看”指定角色且未询问具体配装数据时，优先调用 `genshin_card` 生成并发送角色卡片图片。
- 将明确询问属性、武器、圣遗物、命座、天赋或配装分析的请求限定为调用 `genshin_character_info`。
