# 从哪里开始

在 Teams 对话中搜索批准的共享 PPTX，展示来源、版本和数据时间，确认选页及顺序后，复用原页生成可编辑初稿。新增模板功能：上传 PPT 模板后，可以用于新初稿，也可以给已完成的初稿更换模板。

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
.venv/Scripts/python.exe scripts/run_template_demo.py
```

macOS/Linux：

```text
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python scripts/run_demo.py
.venv/bin/python scripts/run_template_demo.py
```

脚本搜索合成样例，模拟提交已确认的三页，查询任务并保存 `examples/output/Demo_Draft.pptx` 和来源 JSON。它不会调用微软服务或 LLM，不能证明真实租户接入已经完成。

## 2. 运行本地接口

Windows 使用 `start-local.cmd`；macOS/Linux 使用 `bash start-local.sh`。首次运行创建本地 `.env`，已有配置保留。访问 <http://127.0.0.1:8000/docs>。本地模式只在回环地址运行。

## 3. 接入组织环境

CSI 按 [交接清单](CSI_HANDOFF_CN.md) 提供可用环境、Entra 身份、Graph 授权、源目录、输出目录和 HTTPS 服务地址。然后按 [Copilot Studio 配置](COPILOT_STUDIO_CN.md) 导入六个工具、设置选页和[模板上传主题](TEMPLATE_WORKFLOW_CN.md)、测试并发布到 Teams。实际渠道能否接收 PPTX/POTX 附件需要租户验证。

只使用一个全体试用者都有访问权的批准资料库。API 的用户认证与 Graph 的应用文件权限是两件事；本版不会自动裁剪每位用户的文件权限。

## 使用边界

- 搜索结果中的较新日期只反映索引内的证据；日期不明或版本冲突需要人工检查。
- 用户确认后才生成；源文件已变化时需刷新、重选并再次确认。
- 保留支持范围内的可编辑内容和备注；可应用上传模板的母版、版式、主题和页面尺寸。原页直接设置的格式保留，复杂页面仍需检查排版。
- 资料输入为 PPTX，模板为 PPTX/POTX；没有 PDF/DOCX 导入、独立聊天界面或额外模型。
- Teams 返回 SharePoint `webUrl`；它遵循输出文件夹现有权限。API `downloadUrl` 需要认证，不能当作普通匿名下载链接。
- 一台实例、一个服务进程，生产配置使用 Entra。详细限制见 [验收清单](ACCEPTANCE.md)。

## V2 继续开发

核心后台现已加入保存故事线、多轮调整章节和顺序、按最新确认版本生成 PPT 的能力。仍需在 Copilot Studio 实际配置对话主题。开始操作请看 [V2 中文指南](V2_WORKFLOW_CN.md) 和 [Copilot Studio 配置](COPILOT_STUDIO_CN.md)。
