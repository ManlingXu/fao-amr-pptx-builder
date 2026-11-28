# PPT Builder maker handoff

Use this pack to reproduce the local agent's workflow in a Dev solution. The four SKILL.md files are maker-authored topic instructions. Each file identifies its inputs, connector calls, decision points and output. Register tools from the existing Swagger definition and bind them to the topic. These Markdown and JSON files are reference configurations; Microsoft creates the importable solution when a maker packages the configured agent in the tenant.

1. Start with the agent identity and sources in [agent-manifest.json](agent-manifest.json). Paste the referenced instructions into the agent and choose a model enabled in the target environment.
2. Configure the team’s approved input and output locations using [knowledge.example.json](knowledge.example.json). The backend performs slide-level retrieval. Test the app identity's actual folder grants and each requester's output access.
3. Use [tool-contracts.json](tool-contracts.json) to locate every parameter and success schema in the Entra connector definition. JSON pointers follow RFC 6901. Generate a tenant-specific connector using the existing exporter before import.
4. Build the four topic stages from the [search](skills/search/SKILL.md), [author](skills/author/SKILL.md), [review](skills/review/SKILL.md) and [export](skills/export/SKILL.md) instructions. Keep the same plan ID and latest revision between stages.
5. Apply the event checks listed in the manifest at their named topic steps. Test a missing citation, a conflicting date, a stale revision, a changed template and a denied user alongside the standard generation case.
6. Record tenant-side results against the [migration guide](../../../docs/studio/MIGRATION.md), [CSI requirements](../../../docs/studio/CSI_REQUIREMENTS.md) and [local evaluation record](../../../docs/studio/evaluation.csv). Complete a controlled Teams test with a real pilot user before requesting wider distribution.
