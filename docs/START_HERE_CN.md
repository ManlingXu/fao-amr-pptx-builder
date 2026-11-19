# 从哪里开始

本版只做一件事：在 Teams 对话中搜索批准的共享 PPTX，展示来源、版本和数据时间，用户确认选页及顺序后，复用原页生成可编辑初稿。

Copilot Studio 提供 LLM；Python 后台负责检索、文件核验、组装和保存。后台不需要另买模型或向量搜索服务。

## 1. 先看本地示例

需要 Python 3.11 或更新版本。在仓库根目录运行：

```text
python -m venv .venv
```

Windows：

```text
.venv/Scripts/python.exe -m pip install -e ".[test]"
.venv/Scripts/python.exe scripts/run_demo.py
```

macOS/Linux：

```text
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python scripts/run_demo.py
```

脚本搜索合成样例，模拟提交已确认的三页，查询任务并保存 `examples/output/Demo_Draft.pptx` 和来源 JSON。它不会调用微软服务或 LLM，不能证明真实租户接入已经完成。

## 2. 运行本地接口

Windows 使用 `start-local.cmd`；macOS/Linux 使用 `bash start-local.sh`。首次运行创建本地 `.env`，已有配置保留。访问 <http://127.0.0.1:8000/docs>。本地模式只在回环地址运行。

## 3. 接入组织环境

CSI 按 [交接清单](CSI_HANDOFF_CN.md) 提供可用环境、Entra 身份、Graph 授权、源目录、输出目录和 HTTPS 服务地址。然后按 [Copilot Studio 配置](COPILOT_STUDIO_CN.md) 导入四个工具、设置明确确认主题、测试并发布到 Teams。

只使用一个全体试用者都有访问权的批准资料库。API 的用户认证与 Graph 的应用文件权限是两件事；本版不会自动裁剪每位用户的文件权限。

## 使用边界

- 搜索结果中的较新日期只反映索引内的证据；日期不明或版本冲突需要人工检查。
- 用户确认后才生成；源文件已变化时需刷新、重选并再次确认。
- 保留支持范围内的原页和可编辑内容；不生成新事实页，不做统一模板或美化。
- 输入仅为 PPTX；没有 PDF/DOCX 导入、独立聊天界面或额外模型。
- Teams 返回 SharePoint `webUrl`；它遵循输出文件夹现有权限。API `downloadUrl` 需要认证，不能当作普通匿名下载链接。
- 一台实例、一个服务进程，生产配置使用 Entra。详细限制见 [验收清单](ACCEPTANCE.md)。
