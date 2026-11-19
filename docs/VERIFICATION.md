# Verification / 验证记录

Review package date: 18 November 2026.

## Current review results

Final integrated local run on 18 November 2026, using Python 3.12 and the available test dependencies:

| Check | Actual result |
|---|---|
| Full regression suite | **106 passed, 2 dependency deprecation warnings, 11.99 seconds** |
| Synthetic HTTP workflow | Search, explicit confirmation, job completion and authenticated download succeeded |
| Synthetic output | **3 slides**, 9 editable text shapes; no assembly warnings |
| Output package integrity | PPTX ZIP integrity passed; all 29 XML/relationship parts parsed |
| Connector export | Both Swagger 2 definitions exactly match the exporter; all four blueprint operation IDs match |
| Shell validation | `bash -n` passed for the Azure deployment wrapper and both shell launch/deployment scripts |
| Deployment preflight tests | 32 mocked-CLI cases; unsafe paths cause no mutating Azure command |
| Deployment source archive | Built successfully; 34 files; integrity and credential/state exclusions checked |
| Independent review | No blocking code defect identified in the three fixes or surrounding integration boundaries |

The two warnings concern an AnyIO pytest compatibility alias and the installed Starlette/httpx TestClient interface. They did not fail the run. Python 3.11/3.12 CI is proposed but has not run on GitHub.

The synthetic demonstration did not call an LLM or Microsoft services and used no organizational source documents. Copilot Studio supplies the conversational model after tenant configuration.

中文：本次最终本地回归为 **106 项通过**，有 2 条依赖弃用提醒；模拟 HTTP 演示完整生成 3 页 PPTX 和来源清单。PPTX 包结构和可编辑文字对象已检查，未进行桌面 PowerPoint 视觉验收。以上结果不等于已经在 Teams 上线。

Run from the repository root after installing `.[test]`:

```text
python -m pytest
python scripts/run_demo.py
python scripts/make_deploy_zip.py
```

The proposed GitHub workflow runs local tests and a synthetic demo only. No commit, push, pull request, GitHub Actions run or live deployment was performed for this review.

## Evidence boundary

Graph and Entra tests use controlled mocks. Local success does not establish real tenant OAuth, resource grants, custom-connector import, policy allowance, hosted connectivity, SharePoint output permissions or Teams publication.

Representative organizational files still require desktop PowerPoint checks. No live deployment is established by shell syntax or mocked Azure CLI checks.

中文：组织内的 OAuth、资源授权、连接器导入、资料权限、运行主机以及 Teams 发布仍需实际配置和验证。真实 PPT 的兼容性仍需用桌面 PowerPoint 检查。
