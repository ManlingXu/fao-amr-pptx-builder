# Copilot Studio to Teams: core setup

This guide uses a standard Copilot Studio agent with a direct custom connector. The local code package is ready for configuration; tenant connectivity and publication must be validated with CSI. UI labels can vary.

## 1. Prepare the environment and backend

CSI supplies maker access, valid nontrial publication eligibility, budget, an approved environment and connector/data-policy allowance. The [CSI handoff](CSI_HANDOFF_EN.md) includes author-group, tenant publication-setting and Teams route checks. Follow the [deployment guide](../deploy/README.md) for the backend.

Set production `AUTH_MODE=entra`, configure Graph access to the approved source and separate output folder, and obtain an approved HTTPS service address reachable by the connector. The source audience must be uniform. A local loopback URL cannot serve a cloud connector.

## 2. Create the agent

Create the Presentation Assistant in the approved environment, enable Microsoft authentication and paste [agent-instructions-en.txt](../integrations/copilot-studio/agent-instructions-en.txt) into Instructions.

It finds existing approved slides, assembles an editable draft after confirmation, and can apply a user-uploaded PowerPoint template. Copilot Studio supplies the LLM; the backend requires no extra model.

## 3. Generate and import the connector

Run from the repository root, replacing every placeholder:

```text
python scripts/export_connector.py --base-url https://YOUR_APPROVED_HOST --auth entra --tenant-id TENANT_GUID --api-app-id API_APP_GUID --output integrations/copilot-studio/connector-ready.json
```

In the agent's Tools area, choose Add a tool, then New tool → Custom connector. Import the generated Swagger 2 file through the custom-connector interface and check Host, Base URL and OAuth settings. The shipped `.invalid` host and zero GUIDs are templates.

CSI configures the connector OAuth client and registers the connector's returned redirect URI. Use tenant-specific v2 authorization/token endpoints, the API's `api://API_APP_GUID/access_as_user` scope plus `offline_access`, and a refresh URL matching the token URL. The API's expected audience must match the issued token.

Use **End user** authentication so the backend receives the requester identity. Create the user connection and test it. See [Microsoft connector setup](https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-connectors) and [OAuth configuration](https://learn.microsoft.com/en-us/troubleshoot/power-platform/power-automate/connections/verify-oauth-configuration).

For a separately approved controlled API-key pilot, export with `--auth api-key` and configure the `X-API-Key` connection centrally. All key holders share one identity; this is not the production identity route.

## 4. Add the six user operations

| Tool | Inputs and intended use |
|---|---|
| `SearchSlides` | `query`, `limit` up to 15, normally `latest_only=true` |
| `GetSlideVersions` | `slide_id` when a date/version conflict needs review |
| `UploadTemplate` | `file_name`, original binary `content_base64`; use the file-input topic/flow |
| `CreateDraft` | Required `title`, ordered unique `slide_ids` (1–20), `confirmed=true`; optional `template_id` |
| `ApplyTemplate` | Completed owned `job_id`, `template_id`, `confirmed=true`, optional `title` |
| `GetDraftStatus` | `job_id`; returns state, warnings, source map and completed link |

For `CreateDraft`, turn off **Allow agent to decide dynamically when to use the tool** and turn on **Ask the end user before running**. Bind the exact confirmed topic variables; do not allow AI to fill the confirmation field. This uses the [tool controls documented by Microsoft](https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-tools-custom-agent).

For `UploadTemplate` and `ApplyTemplate`, turn off dynamic use and bind inputs from the dedicated topic. File bytes must use configured file inputs, never AI-filled strings. Follow the [template workflow](TEMPLATE_WORKFLOW_EN.md) for file bindings, end-user identity and channel limits. The administrator reindex endpoint and raw file download are not user tools.

## 5. Configure the confirmation topic

Use [flow-design.json](../integrations/copilot-studio/flow-design.json) as a blueprint. It is **not an importable agent, flow or solution**.

1. Collect topic, audience, purpose, approximate slide count and requested reporting period.
2. Search and show candidates with source deck/slide, reporting date or uncertainty, and selection reason. Inspect related versions when useful.
3. Store the exact ordered slide IDs and ask the user to confirm that selection. If declined or changed, return to selection.
4. If a template is requested, upload it through the [template topic](TEMPLATE_WORKFLOW_EN.md) and retain its exact ID. On selection confirmation, call `CreateDraft` with the selected IDs, title, `confirmed=true` and optional `template_id`.
5. Retain `jobId`, explain that processing started, and call `GetDraftStatus`. For queued/running jobs, allow a later status check. Show safe errors for failed jobs.
6. Only when completed, show the exact `webUrl`, relevant warnings and source map. Use variable insertion in the topic message so the returned link is preserved.

To change a completed draft later, the template topic calls `ApplyTemplate` and then checks the newly returned job. An explicit user request with a clear draft and template supplies the intent; ask only if the target is ambiguous. The original draft remains available.

The SharePoint `webUrl` uses existing destination permissions. `downloadUrl` is an authenticated API route, not an ordinary Teams browser link. The backend does not push a completion notification.

## 6. Validate and publish

Complete [acceptance](ACCEPTANCE.md) with two real users and representative source files. Confirm that declining selection creates no draft, source changes are caught, ownership works and output files open in desktop PowerPoint. Also validate template upload bytes in the actual published channel, two-user template isolation, and template replacement with representative native content and notes.

Publish, add the Teams channel, and first install for a one-to-one pilot. Share agent access with the pilot audience before distributing the installation link. Broader organization catalog distribution follows CSI's approval process; agent access, installation and document access are separate. See [Microsoft Teams publication](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams).

Record the live results and operational owners before announcing availability.
