# AstrBot 原神角色卡片插件

一个用于 AstrBot 的插件，可以从 [enka.network](https://enka.network/) 获取原神玩家的角色信息并使用 [enkacard](https://pypi.org/project/enkacard/) 库生成角色卡片图片。

## 功能特性

- 通过 UID 查询原神玩家角色信息
- 使用 [enka.network](https://enka.network/) 服务器获取角色卡片图片


## 安装

### 必选依赖：enkacard与字体

本插件使用 Enkacard pip库进行角色卡片图片生成，因此需要安装 **Enkacard库及必要文件**。

一般插件初次安装时就会自动安装。手动安装：给机器人发送```/ysupdate```即可

### 可选依赖：Playwright
用于生成图片，若不安装则使用 Astrbot 自带的文转图功能
```bash
pip install playwright
python -m playwright install

或者
pip install playwright
playwright install
```

### 插件安装1：通过 AstrBot 安装（推荐但暂不可用）

在 AstrBot 插件市场中搜索并找到 **Enkacard** 后安装

### 插件安装2：AstrBot 手动安装

1. 打开 AstrBot 插件页面
2. 点击 ⌈ **+** ⌋ 安装插件
3. 点击 **从链接安装**
4. 输入 ```https://github.com/yzwou/astrbot_plugin_enkacard```

### 插件安装3：手动安装

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

### 查看指定 UID 的角色列表

```
/ys <UID>
```

示例：
```
/ys 269377658
```

### 查看指定角色

```
/ys <UID> <角色编号>
```

示例：
```
/ys 269377658 1
```

角色编号从 1 开始，对应角色列表中的顺序。

## 其他
**图片保存位置**：插件数据目录 *data/plugin_data/astrbot_plguin_enkacard*


- [enka.network](https://enka.network/)
- [enkacard](https://pypi.org/project/enkacard/)
- [AstrBot](https://github.com/AstrBotDevs/AstrBot)

