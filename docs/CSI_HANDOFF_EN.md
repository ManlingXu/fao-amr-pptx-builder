# CSI handoff: Teams PowerPoint Assistant

## Requested service

A Teams agent finds approved source slides, shows sources and reporting dates, asks the user to confirm an ordered selection, and saves an editable draft to an authorized SharePoint location.

The new [template upload workflow](TEMPLATE_WORKFLOW_EN.md) lets users supply a PPTX/POTX design for a new or completed draft. Backend operations are implemented; CSI must bind original attachment bytes and verify file types and size limits on the actual Teams channel. Uploaded templates stay in requester-owned storage and are excluded from the knowledge index.

The package provides code, local synthetic examples, connector templates and configuration instructions. CSI must provision and validate the organizational connection.

## What CSI supplies

| Area | Required decision or configuration |
|---|---|
| Copilot Studio | Approved environment, maker access, valid nontrial author entitlement, tenant enablement and consumption budget |
| Audience and content | One group authorized to read every file in the configured source library; content owner confirms source approval |
| Backend API | Entra API registration/audience, v2 delegated `access_as_user` scope, assigned allowed role or group |
| Connector | OAuth client and returned redirect URI; end-user credentials; permitted custom connector, data policy and network route |
| Template file input | File-input topic/flow, `name` and `contentBytes` mapping, same requester for upload and generation, actual PPTX/POTX channel validation |
| Graph service identity | Application permission and explicit resource grants for source reads and output writes |
| Storage | Separate source/output locations; existing output-folder permissions, retention and maintenance owner |
| Hosting | Approved HTTPS endpoint, outbound Microsoft access, one instance/process and persistent storage |
| Teams | Agent sharing, allowed installation and the intended publication/distribution scope |

The Graph identity, API registration and connector OAuth client have different responsibilities. CSI may reuse approved registrations where appropriate; this does not imply three new app purchases.

For publication errors, CSI checks the applicable author entitlement, tenant enablement, trial-license conflicts, membership in the configured **Copilot Studio authors** group for pay-as-you-go, and the **Publish bots with AI features** tenant setting. Access to an authoring page alone does not prove publication rights. See [Microsoft publication-license troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/power-platform/copilot-studio/licensing/publish-license-error).

Teams custom-app upload is a separate policy check: review the user's **Upload custom apps** app setup policy. Direct Copilot Studio installation links also depend on the organization-wide preview setting; approved organization-catalog distribution has separate app availability/permission controls. CSI must test the chosen route; none is assumed available. Agent sharing and document permissions must also be verified. See [Microsoft custom-app policy guidance](https://learn.microsoft.com/en-us/microsoftteams/teams-custom-app-policies-and-settings).

## Access boundaries

The source index uses Graph application access. It does **not** reproduce each user's individual SharePoint file ACLs. All permitted API users must be allowed to access all configured source content, including embedded chart data and speaker notes.

Entra identifies the requester and restricts API job/status/download access by owner. The saved SharePoint file follows the destination's existing permissions; it is not automatically private to its creator. The service creates no anonymous sharing link.

Use resource-scoped Graph access selected by CSI. Selected permissions require both consent and a resource assignment; `Sites.Selected` is scoped to a site collection, so separate read/write locations can require a different resource arrangement. See [Microsoft Selected permissions](https://learn.microsoft.com/en-us/graph/permissions-selected-overview).

## Configuration and operation

Use [`.env.production.example`](../.env.production.example) and the [deployment guide](../deploy/README.md). Use `AUTH_MODE=entra` in production; API-key mode is limited to controlled pilots and shares one identity across key holders.

The backend verifies the token audience, issuer, signature, expiry, delegated scope and configured group/role. Configure a dedicated role where possible; group-overage memberships are not expanded by this service. API authentication and Graph grants must both work.

For the Azure deployment script, use nonempty child paths under `/home/data/ppt-assistant/`, such as `/home/data/ppt-assistant/drafts` and `/home/data/ppt-assistant/sharepoint-cache`. The script rejects traversal and code-directory paths before changing the app. Live filesystem permissions and symlinks still require host inspection.

Run one process on one instance. Pending/running jobs fail after restart; if a crash occurred immediately after upload, check the output folder for the job ID before retrying. Administrative reindexing uses a separate key and is not a Copilot user tool.

## Funding and acceptance

CSI confirms applicable Copilot Studio entitlement/capacity, connector policies and backend compute/storage charges against the current organizational agreement. No price or free-use entitlement is assumed. This backend calls no separate LLM or vector-search service. See [Microsoft licensing](https://learn.microsoft.com/en-us/microsoft-copilot-studio/billing-licensing).

Before publication, complete [acceptance checks](ACCEPTANCE.md) with two real users, real source/output folders and representative files in desktop PowerPoint. Then follow [Copilot setup](COPILOT_STUDIO_EN.md). Local tests and mock Graph responses do not establish tenant access.
