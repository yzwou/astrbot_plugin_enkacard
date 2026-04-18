# AstrBot 原神角色卡片插件

一个用于 AstrBot 的插件，可以从 [enka.network](https://enka.network/) 获取原神玩家的角色信息并生成角色卡片图片。

## 功能特性

- 通过 UID 查询原神玩家角色信息
- 使用 [enka.network](https://enka.network/) 服务器获取角色卡片图片


## 安装

### 前置依赖：浏览器与字体安装

本插件使用 Selenium 进行浏览器自动化操作，因此需要安装 **Chromium** 或 **Google Chrome** 浏览器。

#### Windows

访问 [Google Chrome 官网](https://www.google.com/chrome/) 下载并安装 Google Chrome。

#### Linux 用户

使用包管理器安装 Chromium 和中文字体：

```bash
# Ubuntu/Debian
sudo apt-get install -y chromium-browser chromium-sandbox fonts-wqy-zenhei

# Fedora
sudo dnf install chromium

# Arch Linux
sudo pacman -S chromium
```

> **Docker 用户注意**：如果 AstrBot 运行在 Docker 容器内，需要在容器中执行上述命令安装依赖。


<details>
<summary><b>macOS 用户</b></summary>

访问 [Google Chrome 官网](https://www.google.com/chrome/) 下载，或使用 Homebrew 安装：

```bash
brew install --cask google-chrome
```

</details>


### 插件安装：通过 AstrBot 安装（推荐）

在 AstrBot 插件市场中搜索并找到 **Enkacard** 后安装

### 插件安装：手动安装

1. 克隆本仓库到 `data/plugins` 文件夹下：

```bash
git clone https://github.com/yzwou/astrbot_plugin_enkacard data/plugins/astrbot_plugin_enkacard
```

2. 安装 Python 依赖：

```bash
cd data/plugins/astrbot_plugin_enkacard
pip install -r requirements.txt
```

3. 重启 AstrBot 使插件生效

## 使用说明

### 查看指定 UID 的角色

```
/角色 <UID>
```

示例：
```
/角色 269377658
```

### 查看指定角色

```
/角色 <UID> <角色编号>
```

示例：
```
/角色 269377658 1
```

角色编号从 1 开始，对应角色列表中的顺序。

## 依赖项

- `selenium>=4.6.0` - 自动化浏览器操作

## 技术说明

本插件使用 Selenium 完成自动化操作：
- 自动访问 enka.network网站
- 模拟用户操作获取角色信息
- 自动下载角色卡片图片

_注：本插件并没有采用enkacard的PyPI库来获取角色图片_

## 注意事项

1. **响应时间**：由于需要浏览器操作，可能需要 10-30 秒
2. **图片保存位置**：插件目录下的 `screen/` 文件夹


- [enka.network](https://enka.network/)
- [AstrBot](https://github.com/AstrBotDevs/AstrBot)
