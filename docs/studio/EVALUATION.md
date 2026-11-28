# Local evaluation

On 28 November 2026, the offline service ran 33 questions in five languages and four file-generation and revision checks against 183 verified presentations (4,697 slides). The publisher catalog contained 184 entries. One PowerPoint file from BSAC differed from its recorded SHA-256, so the downloader excluded it. All 183 verified files were indexed.

| Measurement | Result |
| --- | --- |
| Positive questions with an accepted original page among five index results | 21 of 25 |
| Positive questions with an accepted page in both the index results and the user-facing outline | 20 of 25 |
| Unsupported or future-year questions returning zero results in both interfaces | 5 of 6 |
| Compound questions showing a supported Zambia page and explicitly identifying the unsupported 2099 budget | 2 of 2 |
| Raw candidate excerpts present in the indexed source-page text with a source URL and file hash | 106 of 106 |
| Generated-file and retained-version checks | 4 of 4 |
| All acceptance checks with a passing outcome | 31 of 37 |

The positive cases passed 10/11 in English, 8/9 in Chinese, 1/2 in French, 1/1 in Spanish and 0/2 in Italian. The 25 regression cases include examples used during development. Eight additional questions were checked separately, with three passes. The language counts are too small to establish general accuracy. Lexical overlap and a valid citation establish traceability; a reviewer must still confirm that the selection answers the question.

## Files and timing

The runner generated actual PowerPoint files, reopened them, checked speaker notes and source reports, recomputed original file hashes, and verified original page bounds and slide order. It tested compilation, reconstruction, hybrid generation, a repeated confirmation, and an immutable template-change version. The hybrid example used reconstructed pages. The dedicated UK example verified native compilation of UK-VARSS 2025 slide 3. The original PowerPoint remained byte-for-byte intact after a second version applied a different template.

With the index ready, the median positive check took 0.284 seconds, including a top-five index lookup and an outline request. The median complete artifact check took 0.324 seconds. Times reflect one run on this host. The source download, index preparation, browser delivery and model inference are outside these measurements.

## Issues requiring review

| Observed issue | Affected case IDs | Practical impact |
| --- | --- | --- |
| Italian phrasing missed the expected source page | poultry-use-it, extra-zambia-leaders-it | Record the source name, location and topic in a second query when the initial search finds insufficient evidence. |
| A French candidate was absent from the proposed outline | extra-france-visits-fr | The index retrieved the accepted French slide. The end-user outline still needs improvement. |
| A result was topically close but missed an accepted page | extra-uk-coverage-zh, extra-uganda-dealers-en | Review the passage for the actual question about reporting coverage or training, then verify the original page. |
| An unrelated Spanish astronomy question returned AMR slides | extra-out-of-domain-es | Treat an irrelevant match as a retrieval failure even if it cites a real deck. |
| Source layouts need visual review | export-compilation, export-reconstruction | The compiled Zambia example generated one automated layout error. The field template triggered two warnings. Inspect the flagged slides in PowerPoint before use. |

## Repeat the run

From the repository root, run the following after the approved corpus has been prepared. Use an output directory outside the source corpus to keep the generated files.

```bash
python scripts/evaluate_studio.py --corpus .local/amr --out docs/studio/evaluation.csv --artifacts .local/studio-evaluation
```

The [question bank](evaluation-questions.csv) records expected decks and original page numbers before scoring. The [observation table](evaluation.csv) preserves every outcome, failure, excerpt count and duration. The [fetch and index record](corpus-verification.json) identifies the excluded publisher file. The [model comparison](model-comparison.json) records a separate paired example using the local language model. The tenant must be evaluated separately for authentication, SharePoint, connector calls, Teams delivery and cost.
