# 在聊天中上传并替换 PowerPoint 模板

目标对话：先选定幻灯片或完成一份初稿，再上传模板并说“请把这份 PPT 换成这个模板”。后台输出一份新文件，保留旧初稿和来源表。无需把模板添加到 Knowledge，也不需要让模型读取模板文字后重新生成整份 PPT。

## 已提供的接口

| 工具 | 输入 | 结果 |
|---|---|---|
| `UploadTemplate` | `file_name`、原始文件的 `content_base64` | 当前用户的 `templateId`、版式名称和提示 |
| `CreateDraft` | 已确认选页，加可选 `template_id` | 选页组装后立即应用模板 |
| `ApplyTemplate` | 已完成的 `job_id`、`template_id`、`confirmed=true`，可选 `title` | 新任务，原初稿保留 |
| `GetDraftStatus` | 新任务的 `job_id` | 完成链接、模板信息、提示和原始来源表 |

模板支持 `.pptx` 和 `.potx`，后台接收的原始文件上限为 16 MiB。聊天渠道、连接器或网关可能要求更小的文件。模板的示例页不会加入输出；只有母版与版式中的标志、背景和装饰会被采用。请把需要全程保留的品牌元素放在母版或版式中。

每页优先匹配模板中同类型的版式，未找到时选用正文或空白版式。输出采用模板的母版、主题和页面尺寸，标题占位符使用目标位置，其余原生对象保持可编辑，按相同比例放进目标内容区。原页的独立背景设定会让位给模板背景，但作为普通图片／形状放置的背景对象会随正文保留。显式指定的字体和颜色保留；含动画的源页目前会被拒绝，并给出提示。复杂组合仍需人工检查，系统不会重写正文或进行语义化视觉重设计。

## 配置文件上传主题

这里使用现有标准 Copilot Studio Agent。先更新自定义连接器，添加 `UploadTemplate` 和 `ApplyTemplate`，再配置上传主题。

1. 在 Agent 的 Settings → Generative AI 中启用 File uploads。
2. 新建“更换 PPT 模板”主题。用户已带附件时，先检查 `System.Activity.Attachments` 是否为空，再把对应附件保存到 `Topic.templateFile`。多个附件时，让用户明确哪个是模板，不能默认把第一份资料当模板。
3. 没有模板附件时，添加 Question 节点，Identify 选择 File，打开 Include file metadata，保存为 `Topic.templateFile`。
4. 在附件到达的这一轮立即保存文件变量。后续消息可能改变 `System.Activity.Attachments`。
5. 把文件传给下面的文件上传 flow。上传成功后保存准确的 `templateId` 和 `fileName`，可显示版式名称和提示。
6. 新建初稿时，在原 `CreateDraft` 调用中传入 `template_id`。已有完成初稿时，调用 `ApplyTemplate`。用户明确说“把刚刚这份换成这个模板”已经说明目标和操作；只有目标文件或模板不清楚时才补问。
7. 保存新的 `jobId`，通过 `GetDraftStatus` 查询。仅在 completed 后返回 `webUrl`。上传成功或 queued 均不表示换模板完成。

## 原始文件到接口的映射

建议用一个窄用途的 Agent flow 包装 `UploadTemplate`，避免文件内容经过 LLM 或被当成普通聊天文本。

1. 使用 **When an agent calls the flow** 触发器，新增 File 类型输入，显示名称为 `templateFile`。
2. 主题调用 flow 时，File 输入选择 Custom value，填写下面的 Power Fx。不要使用 Dynamically fill with AI。

```powerfx
{ contentBytes: Topic.templateFile.Content, name: Topic.templateFile.Name }
```

3. 在 flow 中调用自定义连接器 `UploadTemplate`，按下面表格映射。以设计器实际显示的动态内容为准，输入的内部 JSON 键可能不同。

| API 字段 | Flow 动态内容 |
|---|---|
| `file_name` | File 输入的 `name` |
| `content_base64` | 同一 File 输入的 `contentBytes`，已是原始二进制的 Base64 |

不要对已经为 Base64 的 `contentBytes` 再运行 `base64()`，也不要用提取的文本、附件下载 URL 或文件名代替文件字节。若某渠道返回了文件引用，应由受支持的文件输入/连接器解析为真实文件内容后再上传，不能让后台访问任意用户 URL。

4. 使用 **Respond to the agent** 返回 `templateId`、`fileName` 和需要显示的提示。把 `templateId` 绑定到后续工具的 `template_id`。
5. 上传和后续生成请求必须使用同一个请求者身份。Flow 的连接若固定为创建者身份，会破坏每用户模板和任务隔离。生产部署必须确认 End user 连接能把同一用户身份传到后台；做不到时先完成 CSI 的身份传递设计，再开放多人使用。API-key 试用沿用共享身份的原有限制。

也可直接调用自定义连接器，但只有在实际渠道验证 `.Content` 能按接口要求序列化成原始文件 Base64 后使用。文件名或可读文字能显示，不代表二进制已传递。

## 渠道验收与当前边界

仓库提供后台和连接器配置材料，不会自动修改租户中的 Agent、flow 或 Teams 发布。微软当前的标准 Agent 文档将 PPTX 文件输入列为实验功能，POTX 未列在支持清单中。必须分别验证 Test your agent 与实际 Teams 渠道能否接收模板的完整字节；后台支持某扩展名不等于聊天渠道支持它。新版 Microsoft Copilot Agent 的附件支持范围另有说明，不应直接套到现有标准 Agent。

若实际渠道拒绝 `.pptx` 或 `.potx`，不能宣布“聊天上传已上线”。可由 CSI 启用相应支持，或另行配置批准的文件上传入口；不要求用户把敏感模板放到公开下载地址。

验收至少覆盖：上传不同模板后再次替换；切换会话后无模板时补问；两个账号不能互用 `templateId` 或 `jobId`；失败任务不返回完成链接；对含图片、表格、图表和备注的源页检查内容、顺序与可编辑性；输出在桌面 PowerPoint 打开，核对模板标志、背景和宽高比例。

官方依据（核对日期：2026-11-19）：[文件传给 flow、连接器和工具](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/pass-files-to-connectors)、[标准 Agent 文件输入与渠道限制](https://learn.microsoft.com/en-us/microsoft-copilot-studio/image-input-analysis)、[新版 Microsoft Copilot Agent 附件](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/attachments-overview)。
