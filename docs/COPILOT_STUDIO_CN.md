# Copilot Studio 到 Teams：核心配置

本版采用标准 Copilot Studio Agent 直接调用自定义连接器。代码包提供配置材料；真实租户连接与发布仍需 CSI 验证。界面标签可能略有差异。

## 1. 准备环境与后台

CSI 提供创建者权限、有效非试用发布资格、预算、批准环境和连接器／数据策略许可。[CSI 交接](CSI_HANDOFF_CN.md) 包含作者组、租户发布设置和 Teams 路线检查；后台按 [部署说明](../deploy/README.md) 配置。

生产使用 `AUTH_MODE=entra`，配置 Graph 对批准源库和独立输出目录的访问，取得连接器能访问的 HTTPS 地址。全部用户必须有权访问源库全部内容。本机回环地址不能用作云连接器地址。

## 2. 创建 Agent

在批准环境创建 Presentation Assistant，启用 Microsoft 登录，将 [agent-instructions-en.txt](../integrations/copilot-studio/agent-instructions-en.txt) 粘贴到 Instructions。

唯一任务是搜索批准的原有幻灯片，经用户确认后组成可编辑初稿。Copilot Studio 提供 LLM，后台不需要额外模型。

## 3. 生成并导入连接器

在仓库根目录运行，并替换所有占位值：

```text
python scripts/export_connector.py --base-url https://YOUR_APPROVED_HOST --auth entra --tenant-id TENANT_GUID --api-app-id API_APP_GUID --output integrations/copilot-studio/connector-ready.json
```

在 Agent 的 Tools 选择 Add a tool，再选 New tool → Custom connector。进入连接器界面后导入生成的 Swagger 2 文件，核对 Host、Base URL 和 OAuth。随包的 `.invalid` 地址和全零 GUID 只是模板。

CSI 配置连接器 OAuth 客户端，并注册连接器返回的 redirect URI。使用租户专用 v2 authorization/token 地址；Scope 为 `api://API_APP_GUID/access_as_user` 加 `offline_access`；Refresh URL 与 Token URL 相同。实际 token 的 audience 必须匹配后台配置。

工具认证选 **End user**，使后台识别实际请求者。建立用户连接并测试。参见 [微软连接器配置](https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-connectors) 和 [OAuth 配置](https://learn.microsoft.com/en-us/troubleshoot/power-platform/power-automate/connections/verify-oauth-configuration)。

如另行批准 API-key 受控试用，可用 `--auth api-key` 导出，并集中配置 `X-API-Key` 连接。持有同一密钥的人共享一个身份；生产使用 Entra。

## 4. 只添加四个用户工具

| 工具 | 输入和用途 |
|---|---|
| `SearchSlides` | `query`、最多 15 条的 `limit`，通常 `latest_only=true` |
| `GetSlideVersions` | `slide_id`；核对日期或版本冲突 |
| `CreateDraft` | 必填 `title`、1–20 个不重复且有序的 `slide_ids`、`confirmed=true` |
| `GetDraftStatus` | `job_id`；返回状态、提示、来源表与完成链接 |

为 `CreateDraft` 关闭 **Allow agent to decide dynamically when to use the tool**，开启 **Ask the end user before running**。输入绑定到已确认的主题变量，不让 AI 填写确认字段。对应设置见 [微软工具控制](https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-tools-custom-agent)。

管理员重建索引和文件下载接口不添加为普通用户工具。

## 5. 配置明确确认主题

参照 [flow-design.json](../integrations/copilot-studio/flow-design.json) 配置。它是**蓝图，不是可导入的 Agent、flow 或 solution**。

1. 收集主题、受众、用途、大致页数和数据时间范围。
2. 搜索并显示候选原始文件／页码、数据日期或不确定性、推荐理由；必要时查看相关版本。
3. 保存准确的有序 slide ID 列表，询问用户是否确认这些页和顺序。否定或修改时回到选页。
4. 确认后才用该列表、标题和 `confirmed=true` 调用 `CreateDraft`。
5. 保存 `jobId`，说明已开始处理，再调用 `GetDraftStatus`。仍在排队／运行时允许稍后查询；失败显示安全错误。
6. 仅在 completed 时显示原样返回的 `webUrl`、相关提示和来源表。通过主题消息的变量插入保留准确链接。

SharePoint `webUrl` 使用输出目录已有权限；`downloadUrl` 是需认证的 API 地址，不能当作普通 Teams 浏览器下载链接。后台没有主动推送完成通知。

## 6. 验证和发布

按 [验收清单](ACCEPTANCE.md) 使用两位真实用户和代表性资料，确认拒绝选页不会生成、源文件变化会阻止旧选择、任务所有权生效，且输出能在桌面 PowerPoint 正常编辑。

Publish 后添加 Teams 渠道，先安装到一对一会话试用。先分享 Agent 使用权限，再提供安装链接。组织目录分发按 CSI 审批流程执行；Agent 权限、安装权限和文档权限分别验证。参见 [微软 Teams 发布说明](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams)。

记录实际验收结果、维护人与费用负责人后，再宣布组织可用。
