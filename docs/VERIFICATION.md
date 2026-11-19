# Verification / 验证记录

Local verification date: 19 November 2026, Python 3.12.

## Current results

| Check | Actual result |
|---|---|
| Full regression suite | **134 passed**, 2 dependency deprecation warnings, 9.05 seconds |
| Existing synthetic HTTP workflow | Search, confirmed selection, job completion and authenticated three-slide download succeeded |
| Template HTTP workflow | Uploaded two synthetic templates, created a styled draft, changed its template again and downloaded both results |
| Revision preservation | Original output bytes, ordered source map, slide count and speaker notes retained |
| Native evidence | Tests retain editable text, filled picture/chart/table placeholders, chart values/workbook, image bytes and notes |
| Template design graph | Tests verify target master/layout/background/theme/page dimensions, absolute relationships, POTX and repeated changes |
| Upload protection | Invalid, macro-enabled and oversized uploads rejected; requester ownership, private index separation, persistence and stored-byte checks pass |
| Connector contracts | Upload, create, apply and search required inputs and bounds match API models for both authentication exports |
| Visual inspection | Blue and green synthetic outputs converted to PDF with LibreOffice; first pages inspected for background, branding and text fit |
| Source packaging | Deployment ZIP built successfully; changed files pass `git diff --check` |
| Independent review | No remaining blocking defect identified; optional template response allows null for unstyled jobs |

The two warnings concern an AnyIO pytest compatibility alias and the installed Starlette/httpx TestClient interface. They did not fail the tests.

Both HTTP demonstrations used synthetic documents. They called neither Microsoft services nor an LLM. Template example pages are excluded from the generated draft. Tests cover unsupported input failure without overwriting an existing output, including rejection of animated source slides.

中文：**134 项测试通过**；完整验证了“上传模板 → 生成初稿 → 再换一个模板”的后台流程。原初稿、来源、文字和备注保留，图片、表格和图表有原生对象保留测试。合成样例已用 LibreOffice 渲染检查，未进行桌面 PowerPoint 验收，也不代表 Teams 已上线。

## Reproduce

After installing `.[test]`, run from the repository root:

```text
python -m pytest
python scripts/run_demo.py --output build/demo
python scripts/run_template_demo.py --output build/template-demo
python scripts/make_deploy_zip.py
```

The GitHub workflow includes both local demonstrations. Its configured Python 3.11/3.12 matrix is separate from the observed local Python 3.12 run.

## Evidence boundary

Graph and Entra integration tests use controlled mocks. Actual tenant OAuth, Graph grants, connector import, file-input capability, requester propagation, hosting, SharePoint permissions and Teams publication require CSI configuration and validation. In particular, backend PPTX/POTX support does not establish that a specific chat channel accepts and passes those file bytes. See the [template guide](TEMPLATE_WORKFLOW_EN.md).

The engine adopts template masters/layouts/theme and fits native objects uniformly. It retains direct source formatting. Designs placed only on template example slides are excluded. Representative organizational files still require desktop PowerPoint checks for layout, font availability and supported feature compatibility.
