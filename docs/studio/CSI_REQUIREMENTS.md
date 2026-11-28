# CSI requirements and pilot budget

PPT Builder turns an employee’s request into an editable presentation assembled from approved source slides. The proposed pilot connects a Copilot Studio agent in Teams to a Python presentation service and a SharePoint source/output library. CSI can use this brief to identify the minimum entitlements, hosting route, ownership and incremental cost.

## Request for the platform teams

| Owner | What to confirm | Reply requested |
|---|---|---|
| Power Platform administrator | Approved Dev/Test environments, Dataverse capacity, author eligibility, maker role/group, permissions to create custom connectors and solutions | Environment names, role/group, approval route and lead time |
| Microsoft 365 / Teams administrator | Pilot group, app policy for the Teams and Microsoft 365 channel, sharing scope and org-catalog submission authority | Pilot install route, approver and distribution policy |
| Entra administrator | API audience, delegated access_as_user scope, role or group and OAuth client for end-user authentication | Registration owners, redirect URI process, consent and credential rotation owner |
| SharePoint / Graph administrator | Graph identity with resource-scoped source read and destination write grants, retention and output visibility | Source and output sites, access model, document owner and retention |
| Hosting and security | Existing HTTPS host, persistent storage for index/drafts, TLS, secret storage, monitoring, backup and data-policy classification | Hosting owner, reachable endpoint, capacity limits, expected charges |
| Licensing / procurement | Maker and pilot-user entitlements, Copilot credit route, connector/flow use rights, available capacity and billing owner | Existing coverage, incremental annual and pilot-period quotes in the contract currency |

**Access decision.** Limit the first pilot to users who can read the whole indexed corpus, including notes and embedded content. The Python service enforces requester ownership of jobs. SharePoint controls access after the output is written. If source access differs by user, implement security-trimmed retrieval or split corpora by authorized group before extending the pilot. [Project access model](https://github.com/ManlingXu/fao-amr-pptx-builder/blob/main/docs/CSI_HANDOFF_EN.md)

**Separate purchasing decisions.** The existing Python connector path can use Copilot Studio for language orchestration. A separate paid model endpoint is optional. An agent flow is needed only if the chosen orchestration or attachment path requires it. Ask CSI to verify connector/flow use rights for the final design and pilot audience. [Copilot licensing](https://learn.microsoft.com/en-us/microsoft-copilot-studio/billing-licensing)

## Cost worksheet

| Cost item | How to estimate | Amount for CSI to confirm |
|---|---|---|
| Local offline rehearsal | Use an existing computer and the offline engine | External model and Copilot usage charges from this mode: zero |
| Teams / Copilot author and user entitlement | Count makers and pilot users by existing entitlement. Check authenticated user identity and invoked features. | Existing coverage and incremental annual seat quote |
| Metered Copilot activity | Multiply measured billable credits per completed deck by monthly deck volume. Include retries and revisions. | PAYG rate or capacity allocation under the tenant agreement |
| Hosting and storage | Monthly service hours, persistent GB, monthly file growth, egress and logs | Existing allocation or incremental monthly charge |
| Optional model | Measure input/output tokens per draft and multiply by the approved provider’s model rates | Separate budget, data approval and owner if enabled |

**Illustration in USD.** Microsoft lists USD 0.01 per billable Copilot Credit on pay-as-you-go. At a hypothetical 5,000 billable credits each month, the consumption line would be USD 50 per month, or USD 600 over 12 such months. One 25,000-credit monthly capacity pack is listed at USD 200 per month billed annually, equivalent to USD 2,400 per year before organization-specific terms. Determine the billable share from pilot telemetry. Eligible authenticated employee usage can be included with Microsoft 365 Copilot under the relevant conditions. These figures are public reference prices and exclude seats, host, storage, tax and optional model charges. [Microsoft licensing guidance](https://www.microsoft.com/licensing/guidance/Microsoft-Copilot-Studio) · [Billing conditions and rates](https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-messages-management)

### Ticket text for CSI

We would like to pilot an internal PPT Builder agent in Teams. The agent would use Copilot Studio, an Entra-authenticated custom connector to our Python presentation service, and a restricted SharePoint source library and output location. Could you confirm the Dev/Test environments, maker and connector permissions, Teams pilot distribution policy, Graph resource grants and approved hosting option? Please identify the existing licensing coverage, any incremental cost for a pilot and one year of use, and the technical and procurement contacts for implementation.
