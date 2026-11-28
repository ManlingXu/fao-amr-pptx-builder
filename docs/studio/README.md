# PPT Builder Studio

PPT Builder searches a slide library, shows the original page behind each selection and creates editable PowerPoint presentations with speaker notes. Teams Mode is the presenter’s chat workspace. Developer Mode shows the instructions, tools, knowledge and configuration behind the experience. The local server can also be shared through a temporary password-protected tunnel.

| Reader | Guide |
|---|---|
| Presenter or colleague opening the demo | [Installation and user guide](USER_INSTALLATION.md) |
| Chinese-speaking demo host | [Windows commands and five-minute walkthrough](DEMO_CN.md) |
| Developer maintaining the local or browser application | [Architecture, component inventory, governance and roadmap](DEVELOPER.md) |
| Maker moving the agent into Teams | [Copilot Studio deployment and migration](MIGRATION.md) |
| IT administrator or budget owner | [CSI requirements, pilot budget and ticket](CSI_REQUIREMENTS.md) |

The reviewed 28 November 2026 run verified 183 original presentations and 4,697 slides from 184 catalogue records. Counts depend on the local verified manifest and the publishers’ files. The portable browser edition contains 40 bilingual evidence summaries linked to pages in six of the original decks. The source repository includes instructions to retrieve original files for local use.

[Open Teams Mode](https://ppt-builder-studio.light-sun-3036.chatgpt.site) · [Open Developer Mode](https://ppt-builder-studio.light-sun-3036.chatgpt.site/studio.html)

## Quick start

With Python 3.11+ on Windows, open PowerShell in the repository root and run `.\start-studio.cmd`. On macOS or Linux use `./start-studio.sh`. Open `http://127.0.0.1:8768/`. Begin with the offline engine. The first dependency installation needs internet access. The developer view is at `/studio.html`; use the credentials printed by your local host.
