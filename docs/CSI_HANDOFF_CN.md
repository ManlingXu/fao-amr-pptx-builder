# CSI 交接：Teams PowerPoint 助手

## 需要接入的服务

Teams Agent 搜索批准共享库中的原有幻灯片，展示来源与数据时间；用户确认选页和顺序后，生成可编辑初稿并保存到有权限控制的 SharePoint 位置。

新增[模板上传和替换](TEMPLATE_WORKFLOW_CN.md)：用户上传 PPTX/POTX 模板后，可用于新初稿或替换已完成初稿的模板。后台接口已实现；CSI 需要接通附件原始字节传递，并在实际 Teams 渠道验证文件类型和大小限制。模板只进入请求者的私有存储，不进入知识库索引。

交付包提供代码、合成样例、连接器模板和配置步骤。组织接入由 CSI 提供真实配置并验收。

## CSI 需要提供什么

| 项目 | 需要的决定或配置 |
|---|---|
| Copilot Studio | 批准环境、创建者权限、有效非试用作者资格、租户启用和使用量预算 |
| 受众和内容 | 一个可访问源库全部文件的试用组；内容负责人确认资料获准使用 |
| 后台 API | Entra API 应用及 audience、v2 委托范围 `access_as_user`、允许的角色或组 |
| 自定义连接器 | OAuth 客户端与返回的 redirect URI；使用者身份；数据策略与网络放行 |
| 模板文件输入 | File 输入主题／flow，`name` 和 `contentBytes` 映射，上传及生成使用同一请求者身份；PPTX/POTX 实际渠道验证 |
| Graph 服务身份 | 应用权限加具体资源授权，分别满足源资料读取和结果写入 |
| 文件位置 | 分开的源目录和输出目录；输出权限、保留期与维护负责人 |
| 后台服务器 | 批准的 HTTPS 地址、微软服务出站访问、单实例／单进程和持久存储 |
| Teams | Agent 使用权限、安装许可和发布／分发范围 |

Graph 服务身份、API 应用和连接器 OAuth 客户端职责不同。CSI 可以按现有架构复用批准的注册；不代表必须新买三个应用。

如发布报许可错误，CSI 检查适用的作者资格、租户启用、试用许可冲突、按量付费下配置的 **Copilot Studio authors** 组成员，以及 **Publish bots with AI features** 租户设置。能打开创建页面不代表有发布权限。参见 [微软发布许可排查](https://learn.microsoft.com/en-us/troubleshoot/power-platform/copilot-studio/licensing/publish-license-error)。

Teams 自定义应用上传需单独检查使用者应用设置策略中的 **Upload custom apps**。Copilot Studio 直接安装链接还受组织级 preview 设置控制；已批准的组织目录分发使用独立的应用可用性／权限控制。CSI 必须测试所选路线，不能假定已开放。Agent 使用权和文档权限仍分别验证。见 [微软自定义应用策略](https://learn.microsoft.com/en-us/microsoftteams/teams-custom-app-policies-and-settings)。

## 必须对齐的权限边界

索引使用 Graph 应用身份，**不会**按每位用户的 SharePoint 文件 ACL 自动裁剪。所有允许调用 API 的人，都必须有权查看配置源库全部内容，包括备注和图表内嵌数据。

Entra 用来识别请求者，并限制 API 任务、状态和下载的所有者访问。保存到 SharePoint 的文件遵循输出文件夹已有权限，不会自动变成仅创建者可见。服务不会创建匿名分享链接。

由 CSI 选择合适的 Selected 权限范围。Selected 权限需要同意授权及具体资源分配；`Sites.Selected` 是站点集级别，源目录与输出目录的不同读写范围可能需要调整资源安排。见 [微软 Selected 权限说明](https://learn.microsoft.com/en-us/graph/permissions-selected-overview)。

## 配置和运行

使用 [`.env.production.example`](../.env.production.example) 和 [部署说明](../deploy/README.md)。生产使用 `AUTH_MODE=entra`；API-key 只用于受控试用，持有同一密钥的人共享一个身份。

后台检查 token 的 audience、issuer、签名、过期时间、委托范围和配置的组／角色。可采用专用角色；本服务不会查询组成员过多时省略的完整组列表。API 登录和 Graph 文件授权都要单独验证。

Azure 部署脚本要求持久目录是 `/home/data/ppt-assistant/` 下的非空子路径，例如 `/home/data/ppt-assistant/drafts` 和 `/home/data/ppt-assistant/sharepoint-cache`。路径穿越或代码目录在应用修改前被拒绝。实际文件系统权限和软链接仍由服务器管理员检查。

仅运行一台实例、一个进程。重启后未完成任务标记失败；如果上传后立即崩溃，重试前应按 job ID 检查输出文件夹。管理员重建索引用独立密钥，不暴露为普通 Copilot 工具。

## 费用和验收

CSI 根据实际组织协议确认 Copilot Studio 资格／容量、自定义连接器政策及后台计算／存储费用。本说明不假定价格或免费资格。后台不调用独立 LLM 或向量搜索服务。见 [微软许可说明](https://learn.microsoft.com/en-us/microsoft-copilot-studio/billing-licensing)。

发布前按 [验收清单](ACCEPTANCE.md) 使用两位真实用户、真实源／输出目录和代表性文件，在桌面 PowerPoint 中检查。再按 [Copilot Studio 配置](COPILOT_STUDIO_CN.md) 完成发布。本地测试与模拟 Graph 响应不能证明真实租户权限已开通。

## V2 规划数据与 Agent 配置

V2 会在 `DRAFTS_PATH/plans/` 保存属于具体请求者的章节规划、选页和版本号。CSI 应把它与任务文件、上传模板一并纳入持久存储、保留期、备份和访问控制。V2 的 Python 代码不需要新增独立 LLM、向量数据库或 Azure 产品，但**四个新增接口不会因 GitHub 更新而自动出现在 Copilot Studio Agent 中**。需要在批准环境导入连接器、按照 [V2 指南](V2_WORKFLOW_CN.md) 配置主题变量、保存当前 revision，用户明确确认最新选页与模板后才允许调用 `CreateDraftFromPlan`。请用两个真实账号验证权限、版本冲突、持久存储及授权费用。
