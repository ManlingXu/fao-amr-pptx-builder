# Installation and user guide

Use the browser demonstration for a quick walk-through with a colleague. Run the local application for your own source presentations, an uploaded template, a local model or an optionally enabled OpenAI API connection.

## Install and open the app

1. Download and extract the delivery package, or clone [the source repository](https://github.com/ManlingXu/fao-amr-pptx-builder). Install Python 3.11 or later. In Windows PowerShell, open the directory containing the launchers.
2. Run `.\start-studio.cmd` on Windows or `./start-studio.sh` on macOS/Linux. The initial installation creates a virtual environment and installs dependencies. Wait for the host address and role credentials. Open `http://127.0.0.1:8768/` in your browser.
3. The server prefers a prepared corpus. To point at an existing one run `.\start-studio.cmd --corpus "D:\my-library"`. That folder must contain `verified.csv` and `presentations/`. To retrieve the catalogue from its original publishers, use the code below once the virtual environment is installed. A new clone can start with the included public-source sample.
4. To share the full local workflow temporarily, install [cloudflared](https://developers.cloudflare.com/tunnel/downloads/), then run `.\start-studio.cmd --tunnel`. Send the printed HTTPS address and a visitor password to the intended participant by separate channels. Keep the computer connected. Shut down with Ctrl+C or `.\stop-studio.cmd`. The macOS/Linux launcher and stop scripts accept the analogous calls.

```powershell
.\.venv\Scripts\python.exe scripts\prepare_amr_corpus.py
.\start-studio.cmd
```

### Reuse a Windows computer with an older Python setup

Run `py -0p` to list installed interpreters. If the project's existing `.venv` uses Python 3.10 or earlier, stop the app and preserve that environment by renaming the folder. From the repository root, create a new environment with an installed supported version, for example `py -3.12 -m venv .venv` or `py -3.11 -m venv .venv`, then start Studio. If only older interpreters appear in the list, install Python 3.11 or 3.12 first. The original presentation library can still be selected with `--corpus`.

### Check which material is open

| Edition | Source collection | Expected output |
|---|---|---|
| Browser demonstration | 40 bilingual summaries mapped to original pages in 6 public presentations | Editable summary slides, original-page links and two reports |
| Local starter | Offline starter built by the launcher from the bundled sample if a full corpus is unavailable | Reproducible evidence demonstration without retrieving the full source collection |
| Local original corpus | The 28 November run verified 183 of 184 catalogue entries, containing 4,697 slides | Source-aware native or rebuilt slides, depending on the selected mode and source compatibility |

The host’s live count is the reference for the current session. A publisher-side file change can cause its recorded SHA-256 check to fail and the deck to be excluded.

## Build a presentation

1. **Set the brief.** In Deck settings choose the audience, slide count, output language and template. Optionally set a minimum publication year. Start with “Create four slides on antimicrobial stewardship training for veterinary extension officers.” A narrower subject works best when the selected collection has relevant pages.
2. **Inspect the evidence.** Review each outline item’s source, original page, date and excerpt. Fewer results than requested indicate a coverage gap. Relax the date filter or change the topic to find additional support.
3. **Revise in chat.** Try “Why slide 2?”, “Move slide 2 to slide 1” or “Change length to 3 slides”. Use a model-enabled local session for open-ended rewriting. In the browser edition, supported commands and curated material determine the response.
4. **Generate and review.** Confirm the outline, download the PPTX, source report and QA report, and open the deck in PowerPoint. Inspect the speaker notes, figures, source context, text fit and permissions for reused material. To compare templates, export another version and keep both files before ending your session.

| Local generation mode | What you get | When to choose it |
|---|---|---|
| Compilation | Selected native source slides when compatible, with source references. Read warnings if reconstruction was needed. | The original chart, table or layout is important. |
| Reconstruction | Editable evidence-based pages. Model-enabled drafting can adapt supported text to the requested audience and language. | You need a short briefing or a different structure. |
| Hybrid | A mixture of original and rebuilt pages selected by source-page structure. | You want to retain data-heavy pages alongside narrative explanations. |

The browser edition uses public page summaries and supports editable PPTX plus two JSON reports. Its source-style layouts recreate those summaries. For original Office objects, run the local edition with the relevant publisher files. Local offline mode can preserve source-language text. Review translations and scientific claims before distributing a presentation.

### Model options on the host

For local model-assisted dialogue, install Ollama, run `ollama pull qwen3:4b` and confirm the model is listed by `ollama list`. Select Ollama in local Deck settings. The integration uses the local address `127.0.0.1:11434`. The host can override the model tag through `PPT_STUDIO_OLLAMA_MODEL`. [Ollama on Windows](https://docs.ollama.com/windows)

For OpenAI, the host must explicitly enable the service and supply a server-side project API key. Developer access is the default for this option. Follow the [PowerShell setup and budget instructions](https://github.com/ManlingXu/fao-amr-pptx-builder/blob/main/docs/studio/DEMO_CN.md). The shared browser edition cannot connect to the host’s private credentials.
