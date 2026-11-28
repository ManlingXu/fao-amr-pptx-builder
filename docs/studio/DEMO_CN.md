# PPT Builder 演示手册

用 Teams Mode 展示同事如何提出需求、核对原页证据、修改草稿并下载可编辑的 PowerPoint。用 Developer Mode 给技术同事看指令、知识库、工具和运行设置。下面的步骤从 Windows PowerShell 开始。

## 1. 在自己的电脑上打开

需要 Python 3.11 或更新版本。下载并解压交付包后，在包含 `start-studio.cmd` 的文件夹打开 PowerShell。首次启动会准备 Python 环境和依赖，需要网络。使用已经准备好的环境和本地资料时，离线模式可完成检索和导出。

```powershell
py -0p
.\start-studio.cmd
```

打开 [Teams Mode](http://127.0.0.1:8768/) 开始对话。展示配置时打开 [Developer Mode](http://127.0.0.1:8768/studio.html)，使用启动终端提供的开发者凭据。本机默认访客可直接开始；设置了访客密码时，按页面提示登录。演示完成后，在原窗口按 `Ctrl+C`，也可以在项目目录的新 PowerShell 窗口执行 `.\stop-studio.cmd`。

### 选择要演示的资料

| 资料来源 | 使用方法 | 开始前检查 |
|---|---|---|
| 已整理的完整资料目录 | 指向同时含有 `verified.csv` 与 `presentations` 的目录。命令见下方。 | 查看界面报告的实际课件数和页数。 |
| 刚下载的 GitHub 源码 | 直接启动会优先使用准备好的本地库，否则使用随项目提供的示例。要取得完整原件，可运行下方准备命令。 | 首次下载取决于出版方可用性和校验结果。 |
| 可分享的浏览器演示版 | 打开交付的网址，无需启动自己的电脑。可用资料以网页显示为准。 | 网页上的浏览器模式使用随站附带的公开资料；本机完整库和模型需要本地服务。 |

```powershell
# 已有资料库。将方括号及其中内容一起替换为实际路径。
.\start-studio.cmd --corpus "D:\[资料目录]"
```

```powershell
# 在项目根目录执行。先完成一次启动以安装依赖，再停止服务。
.\.venv\Scripts\python.exe scripts\prepare_amr_corpus.py
.\start-studio.cmd
```

如果原项目的 `.venv` 是 Python 3.10 或更早版本，先停服务，将旧 `.venv` 文件夹改名保存。运行 `py -0p` 查看已装版本，然后用 `py -3.12 -m venv .venv` 创建新环境；若安装的是 3.11，将命令改为 `py -3.11 -m venv .venv`。再运行启动脚本。只有旧版本或找不到 `py` 时，先安装带 Windows launcher 的 Python 3.11 或 3.12。完整库下载返回失败项时，保留成功文件，执行 `.\.venv\Scripts\python.exe scripts\prepare_amr_corpus.py --refresh` 重试，再查看实际可用数量。

## 2. 给同事做五分钟演示

1. **从业务需求开始。** 选择离线模式和当前资料库。用英文输入 “Prepare a four-slide briefing on antimicrobial stewardship training for veterinary extension officers.” 也可以在完整库演示 Zambia stewardship outreach 或 poultry policies。用设置面板指定四页、受众和输出语言。
2. **让同事挑一页核对。** 展开该页的证据，展示来源名称、原始页码和来源链接。询问该页是否适用于当前受众。年份缺失时保留不确定性，使用年份筛选时同时观察可用证据数量。
3. **在同一对话里修改。** 将设置改为三页或更换受众，说明希望调整的重点，重新查看草稿。在可用的语言与模式范围内，可比较引用原页和重组文字的效果。
4. **导出并当场打开。** 确认生成，下载 PowerPoint、来源报告和质量报告。用 PowerPoint 打开文件，选中可编辑文字、切换到备注视图，再核对同一页来源。使用另一种模板生成新版，比较两版的布局和来源。
5. **切换开发者视图。** 展示 Instructions、Knowledge、Tools 和 Monitor。用当前运行信息说明资料库、模型设置及调用情况。在独立浏览器的访客会话中，验证访客不能访问开发者运行数据或另一会话的文件。

### 方案 3 · 让同事从另一台电脑操作

Windows 可以通过 `winget install --id Cloudflare.cloudflared` 安装 Quick Tunnel 客户端。安装后重新打开 PowerShell，进入项目目录，运行下列命令。在终端找到临时 HTTPS 网址，将访客凭据单独交给参加演示的人。保留开发者凭据。电脑须保持联网、唤醒，服务及隧道均须运行。关闭后旧网址失效，下一次启动使用新网址。 [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

```powershell
.\start-studio.cmd --tunnel
```

如需手动指定开发者和访客密码，请在启动前设置 `PPT_STUDIO_ADMIN_PASSWORD` 和 `PPT_STUDIO_USER_PASSWORD`，使用两个不同的至少 12 位密码。默认使用离线生成。要结束远程演示，使用上文的停止命令，并在另一浏览器重新打开旧网址检查服务已结束。

## 3. 选择 GPT 或本地模型

服务端启用开关与 API 密钥后，开发者可以在界面选择可用的 OpenAI 模式。使用有余额的 API 项目，将密钥留在本机。ChatGPT 中符合条件的订阅可领取 API credits；领取后应在关联 API organization 的 Billing / Credit grants 确认实际余额和有效期。API 使用量计入对应项目。 [OpenAI 账户关联及额度说明](https://help.openai.com/en/articles/20001626-api-credits-benefit-for-eligible-chatgpt-subscriptions)

下面的 PowerShell 命令会隐藏输入的密钥，设置本次启动的选项。仅在你决定使用 API 额度时执行。演示期间，访客仍使用离线模式；如需为访客开放模型，启动前另行设置 `PPT_STUDIO_GUEST_OPENAI=1`。

```powershell
$env:PPT_STUDIO_ENABLE_OPENAI = '1'
$secret = Read-Host 'OpenAI project API key' -AsSecureString
$env:OPENAI_API_KEY = [Net.NetworkCredential]::new('', $secret).Password
$env:PPT_STUDIO_MAX_CALLS = '3'
.\start-studio.cmd
```

可通过 `PPT_STUDIO_OPENAI_MODEL` 选择拥有访问权的模型。本地服务同时限制请求次数及 token 预算；实际金额随模型价格和 token 数而变。要继续使用免费的离线演示，停止运行、关闭本次 PowerShell 窗口后，从新窗口按第一节启动。项目内的会话数据与运行账本由本机服务管理；服务重启不会恢复已用的调用额度。

### 想演示真实模型，又希望离线运行

本地 Ollama 模式使用自己电脑运行的模型。安装 Ollama for Windows 后，在 PowerShell 执行 `ollama pull qwen3:4b` 并用 `ollama list` 检查模型是否就绪。在本地服务的演示界面选择 Ollama。首次下载需要网络和磁盘空间，生成速度取决于电脑性能。服务默认从 `127.0.0.1:11434` 访问，模型名称可通过 `PPT_STUDIO_OLLAMA_MODEL` 调整。 [Ollama Windows 使用说明](https://docs.ollama.com/windows) · [Qwen3 模型](https://ollama.com/library/qwen3:4b)

### 演示时怎样解释结果

| 同事看到的情况 | 原因和处理方法 |
|---|---|
| 网页上只有少量课件 | 浏览器版展示六份课件的 40 条双语原页摘要。需要展示原始图表或完整资料时，切换到本地完整库。 |
| 要求四页，只收到两页 | 在当前主题、年份和资料范围内仅找到两条合适证据。先检查筛选，再按需缩小题目范围或调整关键词。 |
| 切换中文后，原始图表仍是英文 | 原页图表、图片中的字和离线抽取的原文保留来源语言。需要改写时可选重组模式及可用模型，并人工核对翻译。 |
