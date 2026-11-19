# Upload a template in chat and apply it to a draft

The intended interaction is: select source slides or finish a draft, attach a template, then say “Apply this template to the presentation.” The backend creates a new file, retaining the previous draft and the source map. A template is a per-request file, not a Knowledge source.

## API operations

| Tool | Input | Result |
|---|---|---|
| `UploadTemplate` | `file_name`, original binary file as `content_base64` | Requester-owned `templateId`, layout names and warnings |
| `CreateDraft` | Confirmed slide selection, optionally `template_id` | Assembles source slides and applies the template |
| `ApplyTemplate` | Completed `job_id`, `template_id`, `confirmed=true`, optional `title` | New job that retains the original draft |
| `GetDraftStatus` | New `job_id` | Completed link, template metadata, warnings and original provenance |

The backend accepts `.pptx` and `.potx` up to 16 MiB decoded. A channel, connector or gateway can impose a lower limit. Template sample slides are excluded. Branding must live on a master or layout to appear in the output.

Each slide uses a template layout of the same type when available, with content or blank layouts as fallbacks. The output adopts template masters, themes and page dimensions. Title placeholders use target geometry; remaining native objects stay editable and fit uniformly within the target content area. Slide-level backgrounds give way to the template background. Backgrounds implemented as ordinary pictures/shapes remain with the source content. Explicit fonts and colors are retained. Animated source slides are currently rejected with a warning. Complex compositions need final review; the engine does not rewrite text or perform semantic visual redesign.

## Configure the upload topic

Regenerate and update the custom connector, add `UploadTemplate` and `ApplyTemplate`, and configure a dedicated template topic in the existing standard Copilot Studio agent.

1. Enable File uploads in Settings → Generative AI.
2. If the triggering message already includes a file, check that `System.Activity.Attachments` is nonempty, then capture the intended attachment as `Topic.templateFile`. If several files arrive, establish which file is the template.
3. Otherwise ask for a file with a Question node, Identify = File, and Include file metadata enabled. Save the response as `Topic.templateFile`.
4. Capture the attachment during the upload turn. Later activities can replace `System.Activity.Attachments`.
5. Call the file-upload flow below and retain the exact successful `templateId` and `fileName`.
6. For a new selection, include `template_id` in `CreateDraft`. For an owned completed draft, call `ApplyTemplate`. An explicit request such as “Apply this template to the draft you just made” identifies the action and target; ask again only when the target or template is ambiguous.
7. Store the new job ID and query `GetDraftStatus`. Return `webUrl` only on completed status. A successful upload or queued response is not a completed presentation.

## Pass the original binary file

Use a small Agent flow around `UploadTemplate` so file contents do not pass through an LLM or ordinary conversation text.

1. Add a File input named `templateFile` to the **When an agent calls the flow** trigger.
2. In the topic action, bind the File input using **Custom value**, with this Power Fx record. Do not use **Dynamically fill with AI**.

```powerfx
{ contentBytes: Topic.templateFile.Content, name: Topic.templateFile.Name }
```

3. In the flow, call the custom connector's `UploadTemplate` action with the following dynamic content. Use the actual fields displayed by the designer; internal trigger JSON keys can differ.

| API field | Flow value |
|---|---|
| `file_name` | The File input's `name` |
| `content_base64` | The same File input's `contentBytes`, already Base64 for the original binary |

Do not Base64-encode an already encoded value. Do not substitute extracted text, a file name or a download URL for bytes. If a channel exposes a file reference, resolve it through supported file inputs/connectors. The backend does not fetch arbitrary user URLs.

4. Use **Respond to the agent** to return `templateId`, `fileName` and relevant warnings. Bind that exact ID to subsequent `template_id` inputs.
5. The upload and draft actions must authenticate as the same requester. A flow connection pinned to the maker does not provide user isolation. Validate end-user identity propagation before a multi-user production deployment. If this is unavailable, CSI must resolve the identity design first. API-key pilots retain their existing shared-identity boundary.

Direct connector invocation is also possible after proving that the actual channel serializes `.Content` to the required binary Base64. Displaying a file name or readable text is insufficient evidence of byte transfer.

## Deployment and channel boundary

This repository contains backend behavior and connector configuration materials. It does not change a live agent, flow or Teams publication. Microsoft's current standard-agent documentation lists PPTX input as experimental and does not list POTX. Validate the full binary upload in both Test your agent and the actual Teams channel. Backend file-type support does not establish channel support. The newer Microsoft Copilot agent harness documents a different attachment surface.

If the channel rejects the file, do not announce chat upload as live. CSI can enable supported capabilities or configure an approved upload surface. Users should not be asked to expose internal templates through public download URLs.

Acceptance should cover switching templates twice, a missing attachment, isolation between two users, failed-job behavior, provenance retention and representative source slides with images, tables, charts and notes. Open completed files in desktop PowerPoint and check branding, background, aspect ratio and editability.

Official references, checked 19 November 2026: [Pass files to flows, connectors and tools](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/pass-files-to-connectors), [Standard-agent file input and channel limits](https://learn.microsoft.com/en-us/microsoft-copilot-studio/image-input-analysis), and [Microsoft Copilot agent attachments](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/attachments-overview).
