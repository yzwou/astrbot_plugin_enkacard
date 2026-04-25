import os
import time

from jinja2 import Environment, FileSystemLoader
import json
import asyncio

from playwright.async_api import async_playwright

from .make_enka import *

async def html_to_image(html_file_path: str, screenshot_path: str) -> str:
    """
    将 HTML 文件转换为图片
    
    :param html_file_path: HTML 文件路径
    :param screenshot_path: 截图保存路径
    :return: 截图文件路径
    """
    # 转换为 file:// URL
    file_url = f'file://{html_file_path.replace(os.sep, "/")}'

    async with async_playwright() as p:
        # 启动浏览器（使用 headless=False 可以看到渲染过程）
        browser = await p.chromium.launch(headless=True)

        # 设置固定的视口宽度（1200px），高度自动调整
        context = await browser.new_context(
            viewport={'width': 600, 'height': 800}
        )
        page = await context.new_page()

        # print(f'正在加载页面: {file_url}')

        # 导航到 HTML 页面
        await page.goto(file_url, wait_until='networkidle')

        # 等待角色卡片渲染完成
        await page.wait_for_selector('.char-card', timeout=10000)

        # 等待所有图片加载完成
        await page.evaluate("""() => {
            return Promise.all(
                Array.from(document.querySelectorAll('img')).map(img => {
                    if (img.complete) return Promise.resolve();
                    return new Promise(resolve => {
                        img.onload = resolve;
                        img.onerror = resolve;
                    });
                })
            );
        }""")

        # print('页面渲染完成，正在获取图片信息...')

        # 获取所有角色卡片的图片信息
        char_data = await page.evaluate("""() => {
            const cards = document.querySelectorAll('.char-card');
            const data = [];
            cards.forEach((card, index) => {
                const img = card.querySelector('.avatar');
                const name = card.querySelector('.name')?.textContent;
                const element = card.querySelector('.ele')?.textContent;
                const level = card.querySelector('.lvl')?.textContent;
                data.push({
                    index: index + 1,
                    name: name,
                    element: element,
                    level: level,
                    imageUrl: img?.src,
                    hasError: img?.getAttribute('data-error') === 'true'
                });
            });
            return data;
        }""")

        # 截图保存
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f'\n已保存到: {screenshot_path}')

        await browser.close()

        return screenshot_path


async def role_list_img(uid: str, render: bool = False):
    """
    生成角色列表图片

    :return 图片路径 角色信息
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_time = time.localtime()
    chars = await list_roles_dict(uid)

    # 加载 AvatarExcelConfigData.json 构建映射
    json_path = os.path.join(script_dir, "AvatarExcelConfigData.json")
    with open(json_path, "r", encoding="utf-8") as f:
        char_data_list = json.load(f)

    # 构建 id -> SideIconName 映射（新文件格式为数组）
    map_dict = {}
    for char_info in char_data_list:
        char_id = char_info.get("id")
        side_icon = char_info.get("sideIconName", "")  # 注意：新文件使用小写开头的字段名
        if char_id and side_icon:
            # 提取角色名部分：UI_AvatarIcon_Side_Kazuha -> Kazuha
            name = side_icon.replace("UI_AvatarIcon_Side_", "")
            try:
                map_dict[int(char_id)] = name
            except (ValueError, TypeError):
                pass
        elif char_id:
            map_dict[int(char_id)] = "PlayerBoy"

    # 设置 Jinja2 环境
    env = Environment(
        loader=FileSystemLoader(script_dir),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # 加载模板
    template = env.get_template("characters_template.html")

    # 渲染模板
    output = template.render(
        uid=uid,
        chars=chars,
        map_dict=map_dict,
        json_map=json.dumps(map_dict)  # 转换为 JSON 字符串供 JS 使用
    )

    # 输出到文件
    file_name = f'screen_role_list/{uid}_{local_time.tm_year}{local_time.tm_mon}{local_time.tm_mday}_{time.strftime("%H%M%S")}'
    html_file_path = os.path.join(script_dir, f'{file_name}.html')
    
    # 确保目录存在
    os.makedirs(os.path.dirname(html_file_path), exist_ok=True)
    
    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(output)

    print(f'HTML文件绝对路径: {html_file_path}')

    if render:
        # 使用 Playwright 渲染 html 页面，等待图片加载完成
        screenshot_path = os.path.join(script_dir, f'{file_name}.png')
        await html_to_image(html_file_path, screenshot_path)
        return screenshot_path

    return html_file_path



async def main():
    a = await role_list_img("269377658")
    print(f'AAA：{a}')


if __name__ == "__main__":
    asyncio.run(main())
    print('Done')

