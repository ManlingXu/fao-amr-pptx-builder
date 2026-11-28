# Copilot Studio deployment guide

This guide is for the maker and CSI engineer moving PPT Builder into an organizational Microsoft 365 tenant. The browser screens show the proposed user and maker experience. Build the organization’s agent in its approved Power Platform environment. Use the repository’s existing Entra-authenticated connector API for the Microsoft integration.

## 1. Map the prototype to the pilot

| Demonstrated capability | Implement in the tenant | Evidence to keep |
|---|---|---|
| Teams-style request and preview | Create a Copilot Studio agent, add the English instructions, collect brief and slide count in a topic | Test chat transcript and saved agent version |
| Slide evidence and date | Run the Python search service against the approved source library. Add SearchSlides and GetSlideVersions to the agent. | One returned slide ID traced to its original deck, page and reporting date |
| Multi-turn selection | Use PlanPresentation, RevisePresentationPlan and GetPresentationPlan. Store the current revision and review the selected slide IDs with the requester. | A changed selection and a rejected stale revision |
| Templates and editable output | Call CreateDraftFromPlan with explicit confirmation, then GetDraftStatus. Bind file input for UploadTemplate, then use ApplyTemplate and GetLayoutReport. | PowerPoint file, source map, authorized SharePoint web link |
| Developer Mode | Recreate configuration in the maker environment. Use agent analytics and platform monitoring for the production pilot. | The approved environment, solution version and responsible owner |
| Local reconstruction, notes and reports | Compare each output requirement against the connector schema. Add and validate any fields, tools or storage needed to deliver local-only features through Teams. | A capability-by-capability pass, deferred item or remediation owner |

The local Studio web service and the FastAPI connector expose different interfaces. The following steps target the FastAPI connector and its 12 declared operations. The repository provides a topic design, four prompt blueprints, an English instruction file and Swagger definitions. A tenant solution is created when the maker builds and exports the agent. [Integration files](https://github.com/ManlingXu/fao-amr-pptx-builder/tree/main/integrations/copilot-studio)

## 2. Connect identity, storage and tools

1. **Create the Dev environment.** CSI assigns the maker, security group, eligible authoring entitlement, Dataverse environment access and connector policy. Agree the Test and production environments, release owner and funding route before the pilot.
2. **Set up the documents.** The content owner approves a common source collection accessible to every pilot participant. The Python index uses a Graph service identity. Individual SharePoint source-file permissions are not reapplied by this index. Create a separate destination with the intended file permissions. Native SharePoint knowledge grounding has its own user-permission checks. [SharePoint knowledge](https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-add-sharepoint)
3. **Deploy the connector backend.** Use the approved HTTPS host, one instance and one worker, persistent draft/cache storage and settings from `.env.production.example`. Configure `AUTH_MODE=entra`, the expected audience, allowed role or group, Graph grants and secret storage. Reindex the pilot collection. [Backend deployment](https://github.com/ManlingXu/fao-amr-pptx-builder/blob/main/deploy/README.md)
4. **Create the custom connector.** Replace the three placeholders below with the CSI-supplied host and GUIDs. Use one line in a terminal at the repository root.

```text
python scripts/export_connector.py --base-url https://APP_HOST --auth entra --tenant-id TENANT_GUID --api-app-id API_GUID --output integrations/copilot-studio/connector-ready.json
```

Import the generated Swagger 2 definition in Dev. Register the connector’s redirect URI, configure OAuth and use end-user credentials. Verify the backend receives the correct requester on every tool call. With selected Graph permissions, consent and a resource assignment are separate steps. [Custom connectors](https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-connectors) · [Graph selected permissions](https://learn.microsoft.com/en-us/graph/permissions-selected-overview)

## 3. Build, validate and publish

1. **Implement the topic.** Paste the agent instructions, collect the brief, call search, show sources, retain exact selected IDs and confirm the current plan before file creation. Bind template bytes through a file-input topic or flow. Mutating calls should use the confirmed topic variables. Review optional prompts against the available source IDs. [Maker instructions](https://github.com/ManlingXu/fao-amr-pptx-builder/blob/main/docs/COPILOT_STUDIO_EN.md)
2. **Validate with two pilot identities.** Confirm a user can search approved sources, revise content, generate and open the deck. A second user must be denied the first user's job or API download. Test SharePoint web links separately against the destination’s permissions. Record the sharing audience if colleagues can open each other’s outputs. Check XML/PPTX creation, a damaged upload, missing evidence, a retry, source references, layout and actual desktop PowerPoint rendering.
3. **Promote into Test.** Put the agent and required components in a custom solution, add dependencies, export a versioned release, import into Test, rebind environment variables and connection references, and publish in that environment. Record the source commit, solution version, connector host and smoke-test results. Retain the previous working solution and backend revision for rollback. [Solutions and environment transfer](https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-solutions-import-export)
4. **Enable the Teams pilot.** Publish the agent, connect the Teams/Microsoft 365 channel, assign pilot users and distribute its installation link under tenant policies. Test chat, template handling and download inside Teams. An organization-catalog listing follows the admin approval path. [Publishing and distribution](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams)

### Release record

Record the pilot group, data owner, deployment owner, supported operations, known gaps, cost meter and rollback owner. If a release fails, suspend its distribution, restore the approved solution/backend revisions and retest an existing user’s file and a new draft. Retain other users’ documents according to the agreed retention period.
