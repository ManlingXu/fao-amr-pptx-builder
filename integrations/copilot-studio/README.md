# Copilot Studio integration

This directory defines six user operations: `SearchSlides`, `GetSlideVersions`, `UploadTemplate`, `CreateDraft`, `ApplyTemplate` and `GetDraftStatus`.

| File | Use |
|---|---|
| `openapi-entra.swagger.json` | Swagger 2 OAuth template for production organizational identity |
| `openapi-api-key.swagger.json` | Swagger 2 template for local/controlled pilots; key holders share one identity |
| `agent-instructions-en.txt` | Paste into the agent's Instructions |
| `flow-design.json` | Human-readable topic blueprint; **not an importable agent, flow or tenant solution** |

Regenerate a connector definition with the approved HTTPS host and real identity settings before import. The shipped `.invalid` hostname and zero GUIDs are explicit placeholders.

Use the connector from the agent. Route binary template attachments through a File-input topic/flow as described in the template guide. Configure `CreateDraft` for explicit topic use with user confirmation and bound ordered slide IDs. Administrative reindexing and raw file download are not exposed as ordinary user tools.

Completed Teams delivery uses the authenticated SharePoint `webUrl`. `downloadUrl` is an authenticated API route.

Follow [English setup](../../docs/COPILOT_STUDIO_EN.md) or [中文配置](../../docs/COPILOT_STUDIO_CN.md).

For chat uploads and template replacement, follow [English template workflow](../../docs/TEMPLATE_WORKFLOW_EN.md) or [中文模板流程](../../docs/TEMPLATE_WORKFLOW_CN.md). The backend accepts PPTX/POTX, but actual chat attachment support and end-user identity propagation require channel validation.
