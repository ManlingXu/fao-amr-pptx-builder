# Acceptance checks / 验收清单

## Local code checks

From the repository root after installing `.[test]`:

```text
python -m pytest
python scripts/run_demo.py
```

The local gate covers search/date evidence, version ranking, confirmation and ordered selection, owner-scoped API jobs, source revalidation, native-slide assembly, safe failures and connector input contracts. The demonstration must return a completed, readable PPTX and an ordered source map. See [verification](VERIFICATION.md) for the current evidence.

Focused regression cases also cover oversized SharePoint sources alongside valid files, retained prior index on Graph failures, explicit written reporting dates ahead of later target years, invalid dates and Azure persistent-path rejection before configuration changes.

## Organizational acceptance — CSI still completes

| Check | Expected result |
|---|---|
| Two real users | Entra connector uses each requester; API job ownership works |
| Full source audience | Every allowed user may access every configured source, including notes and embedded data |
| Graph grants | Approved source reads and destination writes succeed; access outside the approved resources fails |
| Search review | Deck, slide, reporting date, uncertainty and related versions can be reviewed |
| Explicit confirmation | Declining or changing a selection does not create the old selection; order matches the confirmed list |
| Changed/deleted source | Source drift blocks creation until refresh and reselection |
| Native-slide fidelity | Representative drafts open in desktop PowerPoint with editable supported objects and correct notes/styles |
| Completed result | Teams shows the exact completed SharePoint link; destination permissions match the approved audience |
| Failures and capacity | Queue full, unsupported source, restart and upload failure produce useful safe errors |
| Publication and operation | Agent sharing, Teams installation, hosting, budget, maintenance and retention are recorded |

Local Graph/Entra mocks and LibreOffice rendering cannot substitute for live tenant or desktop PowerPoint acceptance.

## Supported boundary

- **Inputs:** approved PPTX only; at most 20 unique slides per draft. API searches return at most 15 candidates per request.
- **Sizes:** 64 MiB per source, 256 MiB combined selected source bytes and 128 MiB output.
- **Preservation:** supported native source objects, images, notes and self-contained chart workbooks; required package dependencies are copied. Embedded workbook data is included.
- **Rejection:** mismatched slide/notes canvases, incompatible document-wide styles and unsupported/protected dependencies, including macros, encryption, OLE and linked media/data. This is not a guarantee for every PowerPoint feature.
- **Identity:** one common approved source audience; no per-file user ACL trimming. Entra API job ownership and SharePoint output permissions are separate.
- **Operations:** one process/instance, two draft workers and twelve outstanding jobs. Incomplete jobs fail on restart. No distributed queue or proactive Teams notification.
- **Dates:** evidence-based heuristics and version families require human review when ambiguous. A newer indexed result is not proof of scientific correctness or global currency.

中文要点：本地验收证明代码与合成样例的行为；真实账号、Graph 授权、连接器、Teams 发布、文件权限与桌面 PowerPoint 效果仍由 CSI 验收。只复用批准的 PPTX 原页，保留必要权限与来源控制，不扩展新内容生成或美化功能。
