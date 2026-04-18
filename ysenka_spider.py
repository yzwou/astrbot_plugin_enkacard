"""
enka.network 爬虫 (跨平台版 - 异步版)
功能：支持 UID 查询、角色自动切换、自动下载角色长图
支持系统：Linux / Windows
"""

import asyncio
import os
import platform
import re
import shutil
import subprocess
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException


def get_chrome_version_windows():
    """获取 Windows 系统 Chrome 浏览器版本"""
    try:
        import winreg

        # 尝试从注册表读取 Chrome 版本
        paths = [
            r"Software\Google\Chrome\BLBeacon",
            r"Software\Wow6432Node\Google\Chrome\BLBeacon",
        ]
        for path in paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
                version = winreg.QueryValueEx(key, "version")[0]
                winreg.CloseKey(key)
                return version.split(".")[0]  # 返回主版本号
            except Exception:
                continue
        return None
    except Exception:
        return None


def check_linux_chrome_env():
    """检查 Linux 系统 Chrome/Chromium 环境，返回 (是否可用, 错误信息)"""
    try:
        # 依次尝试可能的命令名称
        for cmd in ["chromium", "google-chrome", "google-chrome-stable", "chromium-browser"]:
            try:
                result = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"✅ 找到浏览器: {cmd} ({result.stdout.strip()})")
                    return True, ""
            except FileNotFoundError:
                continue

        # 如果命令没找到，尝试查找物理路径
        chrome_paths = [
            "/usr/bin/chromium",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
        for path in chrome_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                print(f"✅ 找到可执行文件路径: {path}")
                return True, ""

        error_msg = ("未找到 Chrome 或 Chromium 浏览器。\n"
                     "由于您的环境是 Debian Trixie (Docker)，建议安装 Chromium：\n"
                     "1. apt-get update\n"
                     "2. apt-get install -y chromium chromium-sandbox fonts-wqy-zenhei")
        print(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        return False, f"检查环境时出错: {str(e)}"


def _get_install_command(missing_libs):
    """根据缺失的库提供安装命令"""
    # 常见库到包名的映射
    lib_to_package = {
        "libnss3.so": "nss",
        "libnspr4.so": "nspr",
        "libatk-1.0.so": "atk",
        "libatk-bridge": "at-spi2-atk",
        "libcups.so": "cups-libs",
        "libdrm.so": "libdrm",
        "libdbus-1.so": "dbus-libs",
        "libxkbcommon.so": "libxkbcommon",
        "libX11.so": "libX11",
        "libXcomposite.so": "libXcomposite",
        "libXdamage.so": "libXdamage",
        "libXext.so": "libXext",
        "libXfixes.so": "libXfixes",
        "libXrandr.so": "libXrandr",
        "libgbm.so": "mesa-libgbm",
        "libpango": "pango",
        "libcairo.so": "cairo",
        "libasound.so": "alsa-lib",
        "libxcb.so": "libxcb",
    }
    
    packages = set()
    for lib in missing_libs:
        for lib_pattern, package in lib_to_package.items():
            if lib_pattern in lib:
                packages.add(package)
                break
    
    if not packages:
        return "sudo yum install -y nss nspr atk at-spi2-atk cups-libs dbus-libs libdrm libxkbcommon libX11 libXcomposite libXdamage libXext libXfixes libXrandr mesa-libgbm pango cairo alsa-lib libxcb"
    
    return f"sudo yum install -y {' '.join(packages)}"


def setup_chromedriver_for_windows():
    """Windows 系统下配置 ChromeDriver"""
    try:
        # 方法 1: 尝试使用 Selenium 4.6+ 的 Selenium Manager（自动管理驱动）
        print("尝试使用 Selenium Manager 自动管理 ChromeDriver...")
        return None  # 返回 None 让 Selenium 自动管理

    except Exception as e:
        print(f"Selenium Manager 失败: {e}")

        # 方法 2: 尝试使用 webdriver-manager
        try:
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            print("尝试使用 webdriver-manager...")
            service = Service(ChromeDriverManager().install())
            return service
        except ImportError:
            print("webdriver-manager 未安装，尝试自动管理...")
            return None
        except Exception as e2:
            print(f"webdriver-manager 失败: {e2}")
            return None


async def async_get_character_list(driver):
    """
    异步获取页面左侧所有角色列表
    """
    try:
        # 查找所有角色头像元素
        avatars = driver.find_elements(
            By.CSS_SELECTOR,
            "div.avatar.svelte-dxdrgu.live, div.avatar.svelte-dxdrgu.live.s",
        )

        character_list = []
        for idx, avatar in enumerate(avatars, 1):
            try:
                figure = avatar.find_element(By.CSS_SELECTOR, "figure.chara")
                style = figure.get_attribute("style") or ""
                # 提取图片 URL 中的角色内部 ID
                match = re.search(r"UI_AvatarIcon_Side_([^.]+)\.png", style)
                char_name = match.group(1) if match else f"Unknown_{idx}"
            except Exception:
                char_name = f"Unknown_{idx}"

            character_list.append({"index": idx, "name": char_name, "element": avatar})
        return character_list
    except Exception as e:
        print(f"获取角色列表失败: {e}")
        return []


async def async_switch_character(driver, character_list, target_index):
    """
    异步执行角色切换动作
    """
    try:
        target_element = None
        for char in character_list:
            if char["index"] == target_index:
                target_element = char["element"]
                print(f"找到角色 #{target_index}: {char['name']}")
                break

        if not target_element:
            print(f"未找到角色 #{target_index}")
            return False

        # 检查是否已选中
        class_attr = target_element.get_attribute("class") or ""
        if class_attr.endswith(" s") or " live s" in class_attr:
            print("角色已处于选中状态")
            return True

        # 点击切换并等待渲染
        target_element.click()
        await asyncio.sleep(3)  # 异步等待
        return True
    except Exception as e:
        print(f"切换角色操作失败: {e}")
        return False


async def async_scrape_enka(uid, character_index=None, headless=True):
    """
    异步核心爬取函数

    参数:
        uid: 用户UID
        character_index: 角色编号（从1开始），若为None则不切换角色，下载当前显示的
        headless: 是否无头模式

    返回:
        tuple: (success: bool, result: str, error: str)
            - success: 是否成功
            - result: 成功时返回图片路径，失败时为 None
            - error: 失败时返回错误信息，成功时为空字符串
    """
    uid = str(uid)
    url = f"https://enka.network/u/{uid}"

    # 建立下载目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    screen_dir = os.path.join(current_dir, "screen")
    os.makedirs(screen_dir, exist_ok=True)

    driver = None
    try:
        options = Options()
        if headless:
            options.add_argument("--headless=new")

        # 根据操作系统配置 Chrome 选项
        system = platform.system().lower()
        if system == "linux":
            # Linux 服务器配置
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            print("🐧 检测到 Linux 系统，应用 Linux 特定配置")
        elif system == "windows":
            # Windows 系统配置
            options.add_argument("--disable-gpu")
            print("🪟 检测到 Windows 系统，应用 Windows 特定配置")
        else:
            # macOS 或其他系统
            print(f"💻 检测到 {system.capitalize()} 系统，应用通用配置")

        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        prefs = {
            "download.default_directory": screen_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)

        print("🚀 正在启动 Chrome...")

        # 根据系统配置 ChromeDriver
        if system == "windows":
            # Windows: 尝试自动管理 ChromeDriver
            chrome_service = setup_chromedriver_for_windows()
            if chrome_service:
                driver = webdriver.Chrome(service=chrome_service, options=options)
            else:
                driver = webdriver.Chrome(options=options)
        elif system == "linux":
            # Linux: 直接使用完整路径启动 Chrome，不依赖 PATH 环境变量
            # 按优先级尝试常见的 Chrome 安装路径
            chrome_found = False
            for chrome_path in [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/opt/google/chrome/google-chrome",
                "/usr/local/bin/google-chrome",
            ]:
                if os.path.exists(chrome_path):
                    print(f"✅ 找到 Chrome 二进制文件: {chrome_path}")
                    options.binary_location = chrome_path
                    chrome_found = True
                    break
            
            if not chrome_found:
                # 如果预设路径都没找到，尝试从 PATH 中查找
                chrome_in_path = shutil.which("google-chrome") or \
                                 shutil.which("google-chrome-stable") or \
                                 shutil.which("chromium-browser") or \
                                 shutil.which("chromium")
                if chrome_in_path:
                    print(f"✅ 从 PATH 中找到 Chrome: {chrome_in_path}")
                    options.binary_location = chrome_in_path
                    chrome_found = True
            
            if not chrome_found:
                return (False, None, "在 Linux 上未找到可执行的 Chrome 浏览器。\n\n请安装 Chrome:\nsudo yum install -y https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm\n\n安装后请重启 AstrBot。")

            # 尝试启动 Chrome
            try:
                driver = webdriver.Chrome(options=options)
            except WebDriverException as e:
                error_msg = str(e)
                if "exited. Status code was: 127" in error_msg or "unexpectedly exited" in error_msg:
                    return (False, None, f"Chrome 启动失败 (错误代码 127)，通常是缺少系统依赖库。\n\n请运行以下命令安装依赖:\nsudo yum install -y nss nspr atk at-spi2-atk cups-libs dbus-libs libdrm libxkbcommon libX11 libXcomposite libXdamage libXext libXfixes libXrandr mesa-libgbm pango cairo alsa-lib libxcb")

                return (False, None, f"启动 Chrome 失败: {error_msg}")
        else:
            # macOS: 直接使用 Selenium Manager
            driver = webdriver.Chrome(options=options)

        wait = WebDriverWait(driver, 25)  # 显式等待 25 秒

        print(f"🌐 访问中: {url}")
        driver.get(url)

        # === 注入 Cookie 以强制显示中文 ===
        try:
            # 先删除可能存在的旧 cookie
            driver.delete_cookie("locale")
            # 添加新的 cookie
            driver.add_cookie(
                {
                    "name": "locale",
                    "value": "zh-cn",
                    "domain": "enka.network",
                    "path": "/",
                }
            )
            # 重新访问页面使 cookie 生效
            print("   ✅ 已设置语言为中文 (zh-cn)，重新加载页面...")
            driver.get(url)
        except Exception as e:
            print(f"   ⚠️ 设置 Cookie 失败: {e}")

        # 等待页面核心元素出现
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.avatar")))
        print(f"✅ 页面加载成功: {driver.title}")

        # === 处理角色切换逻辑 ===
        if character_index is not None:
            print(f"\n--- 正在切换到角色 #{character_index} ---")
            await asyncio.sleep(2)  # 异步等待
            character_list = await async_get_character_list(driver)

            if not character_list:
                print("⚠️ 未找到可供切换的角色列表")
            else:
                success = await async_switch_character(
                    driver, character_list, character_index
                )
                if not success:
                    error_msg = f"切换到角色 #{character_index} 失败，请检查角色编号是否正确"
                    print(f"❌ {error_msg}")
                    return (False, None, error_msg)
            print("--- 角色切换处理完成 ---\n")

        # === 按钮点击流程 (针对 Linux 优化) ===

        # 步骤 1: 点击"生成图片"按钮
        print("步骤 1: 查找并点击'生成图片'按钮...")
        try:
            btn_generate = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[data-icon="download-image"]')
                )
            )
            btn_generate.click()
            print("   ✅ 点击成功")
        except Exception as e:
            error_msg = f"无法点击生成按钮，请检查 UID {uid} 是否有效或网页结构是否已更新: {str(e)}"
            print(f"   ❌ {error_msg}")
            error_path = os.path.join(screen_dir, f"error_stage1_{uid}.png")
            driver.save_screenshot(error_path)
            return (False, None, error_msg)

        # 步骤 2: 等待弹窗并点击最终"下载"
        print("步骤 2: 等待渲染并点击'下载'按钮...")

        # 尝试多个可能的按钮选择器（应对网页更新或不同分辨率）
        selectors = [
            'button[data-icon="download"]',
            '.modal button[data-icon="download"]',
            ".modal-content button",
            "a[download]",
        ]

        success_download_click = False
        last_error = ""
        for selector in selectors:
            try:
                # 尝试点击每一个可能的选择器，每个给 5 秒机会
                btn_download = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                btn_download.click()
                print(f"   ✅ 通过 [{selector}] 点击下载成功")
                success_download_click = True
                break
            except Exception as e:
                last_error = str(e)
                continue

        if not success_download_click:
            # 如果失败了，截图看看当时页面长什么样
            debug_img = os.path.join(screen_dir, f"error_debug_{uid}.png")
            driver.save_screenshot(debug_img)
            error_msg = f"无法定位下载按钮，请检查网页结构是否已更新。已保存调试截图至: {debug_img}。最后错误: {last_error}"
            print(f"   ❌ {error_msg}")
            return (False, None, error_msg)

        # 步骤 3: 确认下载
        print("步骤 3: 等待文件写入磁盘...")
        await asyncio.sleep(6)  # 异步等待文件写入

        # 记录下载前的文件列表（用于对比找出新文件）
        # 寻找目录下最新的图片文件
        all_files = [
            os.path.join(screen_dir, f)
            for f in os.listdir(screen_dir)
            if os.path.isfile(os.path.join(screen_dir, f))
        ]
        # 只保留图片文件（png/jpg/webp）
        image_files = [
            f
            for f in all_files
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]
        # 排除掉我们自己保存的 error 截图
        image_files = [
            f for f in image_files if not os.path.basename(f).startswith("error_")
        ]

        if image_files:
            image_files.sort(key=os.path.getmtime, reverse=True)
            latest_file = image_files[0]
            # 验证文件是否是新创建的（60秒内）
            file_age = time.time() - os.path.getmtime(latest_file)
            if file_age < 60:
                print(f"🎉 任务完成！下载文件: {latest_file}")
                return (True, latest_file, "")
            else:
                error_msg = "发现图片文件但都不是最近下载的（可能是旧文件），请检查下载配置"
                print(f"⚠️ {error_msg}")
                return (False, None, error_msg)
        else:
            error_msg = "未发现新下载的文件，请检查 screen 文件夹权限或 enka.network 是否正常"
            print(f"⚠️ {error_msg}")
            return (False, None, error_msg)

    except Exception as e:
        error_msg = f"发生异常: {type(e).__name__}: {str(e)}"
        print(f"🔥 {error_msg}")
        return (False, None, error_msg)
    finally:
        if driver:
            driver.quit()


async def async_main():
    print("====================================")
    print("    Enka.Network 爬虫 (跨平台版)")
    print("====================================")

    # 检测系统
    system = platform.system().lower()
    print(f"📡 当前系统: {platform.system()} {platform.release()}")

    uid = input("请输入 UID (默认 269377658): ").strip() or "269377658"

    char_input = input("请输入角色编号（从1开始，直接回车则不切换角色）: ").strip()
    character_index = int(char_input) if char_input else None

    # 根据系统设置 headless 默认值
    # Linux 服务器通常不需要显示界面，Windows 可以显示方便调试
    if system == "windows":
        headless_input = (
            input("是否使用无头模式？(y/n，默认 n-显示浏览器): ").strip().lower()
        )
        headless = headless_input == "y"
    else:
        headless_input = (
            input("是否使用无头模式？(y/n，默认 y-隐藏浏览器): ").strip().lower()
        )
        headless = headless_input != "n"

    print("\n📋 配置信息:")
    print(f"   UID: {uid}")
    print(
        f"   角色编号: {character_index if character_index else '不切换（使用默认）'}"
    )
    print(f"   无头模式: {'是' if headless else '否'}")
    print(f"   系统: {system.capitalize()}\n")

    result = await async_scrape_enka(
        uid, character_index=character_index, headless=headless
    )

    if not result:
        print("\n❌ 运行失败，请查看报错或 screen 文件夹下的 error 截图。")
    else:
        print(f"\n✅ 成功下载图片: {result}")


def main():
    """同步入口函数（向后兼容）"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
