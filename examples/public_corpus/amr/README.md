# AMR 专题 PowerPoint 演示

[30 个来源网站与数量](SOURCES_CN.md) · [选页原理与 AI 的作用](../../../docs/AMR_SELECTION_LOGIC_CN.md) · [浏览 150 份课件及原始来源](catalog.csv) · [检索测试题](queries.csv) · [综合主题的 120 份演示库](../README.md)

这套资料供本地测试从现有课件中检索、选页和组装 PowerPoint 的流程。2026 年 11 月 24 日下载核对了 **150 份不同的原始 PPTX，共 3,868 页**，原始 PPTX 合计约 973 MB。其中 18 份也在综合演示库中，132 份为新增来源文件。

| 优先检索的内容 | 命令参数 | 课件 | 幻灯片 |
|---|---|---:|---:|
| 兽用抗菌药、农场管理、畜牧业监测 | `--sector animal` | 57 | 1,123 |
| 人、动物与环境共同涉及的政策、研究和公众教育 | `--sector one-health` | 13 | 317 |
| 人医合理用药、处方审计、培训和公众沟通 | `--sector human` | 80 | 2,428 |

面向兽医或 FAO 同事演示时，合用前两个参数，可以在 70 份课件、1,440 页中检索。省略参数会搜索全部三个领域。

## 课件从哪里来

- **农场实践。** 欧盟农户与兽医培训项目入选 32 份，包括捷克两家奶牛场、拉脱维亚兽医与养猪企业的合作，以及意大利家禽业的抗菌药减量。其中 9 份属于同一课程模块，分别说明不同国家的处方、报告或监管规则。`training_country` 指该次培训的举办国，个别主讲人介绍了其他国家的经验。[欧盟培训材料](https://www.amrfvtraining.eu/library/)
- **非洲和亚洲。** 赞比亚材料可定位到与农户和传统领袖沟通、兽医培训和监测政策的具体页。埃塞俄比亚和越南的课件涉及小农户用药与生计，印度课件比较了面向养殖户和兽医的宣传方式。[CwPAMS 合作伙伴工具包](https://commonwealthpharmacy.org/cwpams-toolkit/) · [CGIAR 来源清单](catalog.csv)
- **政策与年度数据。** 法国 Écoantibio 保留一份英文版。年度监测资料有 3 个系列、11 份文件，分别是英国 UK-VARSS 的 2019–2025 报告年、爱尔兰 EARS-Net 的 2022 和 2024 报告年，以及瑞典 Swedres-Svarm 的 2013 和 2014 人医图表。目录的 `issued` 表示已知发布日期，与报告年可能相差一年。[法国农业部](https://agriculture.gouv.fr/le-plan-ecoantibio-2-2017-2021) · [英国兽药管理局](https://www.gov.uk/government/collections/veterinary-antimicrobial-resistance-and-sales-surveillance)

每条记录都有发布者、公开来源、下载地址、主题、原始页数、一个能体现主题的原始页码（`evidence_slide`，从 1 开始）和 SHA-256。少数出版方把 PPTX 放在 ZIP 内，`zip_member` 标出其中的原始文件。收录前检查了原始文件完整性、页数和正文，并排除了发现的翻译副本、几乎相同的版本和 AMR 内容过少的课件。英欧机构和英文材料占比较高。该目录用于测试检索和选页，对全球各地区的覆盖程度不均。

## 在本地演示

在项目根目录按下列顺序运行，使用 Python 3.11 或 3.12 的虚拟环境。下载命令只在首次运行时需要获取全部源文件。重新运行会复用已验证的文件，并重试上次失败的来源。

```bash
python -m pip install -e ".[test]"
python scripts/fetch_public_corpus.py --catalog examples/public_corpus/amr/catalog.csv --corpus-dir .local/amr --workers 4
python scripts/run_public_corpus_demo.py --corpus-dir .local/amr --sector animal --sector one-health --query "What target did the French Ecoantibio plan set to reduce animal exposure to antibiotics?" --interactive
```

候选结果列出课件标题与原始页码。在终端输入 `why 1` 可以查看第一名命中了哪些词、这些词出现在哪里、日期依据及排序分数。选择候选页、核对顺序，输入 `yes` 后生成本地初稿。`source_map.json` 记录各页的出处和校验值。同一组查询也可以用 `--confirm` 测试自动组装。初稿复制兼容的原始页，原来是图片的内容仍是图片。对外分享或改编前，按来源页核对授权和署名；`license` 为空表示未核实具体复用条款。仓库提供目录和代码，源课件按需从发布方下载。

### 10 页赞比亚 AMR 换模板演示

两页示例主要用于检查检索结果。下面的完整演示固定使用同一份赞比亚原始课件中的 10 页真实内容，同时输出原始版、蓝色模板版和绿色模板版。三份 PPT 的内容、顺序、来源记录和备注一致，适合在现场直接比较换模板前后的效果。

| 输出页 | 原始页 | 内容 |
|---:|---:|---|
| 1 | 1 | AMR 与抗菌药物管理标题页 |
| 2 | 2 | 赞比亚 AMR 背景与耐药问题 |
| 3 | 3 | 抗菌药物管理在控制 AMR 中的作用 |
| 4 | 5 | 国家行动计划与五项目标 |
| 5 | 8 | 养殖、生物安全与早期报告措施 |
| 6 | 10 | 广播、会议、培训及农户和传统领袖宣传 |
| 7 | 11 | 合理使用抗生素培训图片 |
| 8 | 15 | 兽医立法、诊疗指南和物种范围 |
| 9 | 17 | 家禽、猪和水产养殖 AMR 监测协议 |
| 10 | 19 | 实验室基础设施和人员能力建设 |

在 Windows PowerShell 的项目根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_amr_ten_slide_showcase.py --corpus-dir .local\amr --output-dir build\amr-ten-slide-showcase
```

结果保存在 `build\amr-ten-slide-showcase`。现场依次打开：

1. `AMR_10_Slide_Original.pptx`：保留原始课件设计。
2. `AMR_10_Slide_Blue.pptx`：同一批内容应用蓝色演示模板。
3. `AMR_10_Slide_Green.pptx`：同一批内容再次更换为绿色演示模板。

脚本还保存 `source_map.json`、`slide_analysis.json`、`layout_decisions.json` 和两份版式检查报告。被问到“每页从哪里来”或“程序为什么选这个版式”时，可以打开这些记录说明。

默认蓝色和绿色模板由脚本生成，只用于清楚证明模板能够切换。也可以换成自己的 FAO 模板：

```powershell
.\.venv\Scripts\python.exe scripts\run_amr_ten_slide_showcase.py `
  --corpus-dir .local\amr `
  --output-dir build\amr-ten-slide-showcase `
  --template-a "C:\Users\徐曼灵\Documents\FAO_Template.pptx" `
  --template-b "C:\Users\徐曼灵\Documents\Second_Template.pptx"
```

请把路径换成电脑上的实际模板文件。模板的颜色、页脚和品牌元素应放在 PowerPoint 的幻灯片母版或版式中；只画在模板示例页上的设计不会自动成为输出背景。

为了让现场每次都得到相同结果，这个本地演示使用预设的 10 页故事线，不调用大语言模型或 Microsoft 服务。它证明 Python 后台能够核对真实来源、组装 10 页、分析页面结构并应用模板。Copilot Studio 中配置的 AI 决策步骤再负责理解自然语言需求、扩展检索词、在真实候选页中重排，以及从模板允许的版式名称中选择布局。

### 两页快速检索检查

以下两个提示分别描述农户宣传与兽医监测。已在动物健康资料中实际运行，并重新打开导出的文件。初稿第 1 页对应赞比亚原课件第 10 页，列出广播、会议、培训及目标人群；第 2 页对应原第 17 页，列出家禽、养猪和水产养殖的监测工作。两页均保留可编辑文字。[赞比亚原始课件](https://drive.google.com/file/d/1sUqmUiCrPjQj25qvbXXYgsQTPYus3NIr/view)

```bash
python scripts/run_public_corpus_demo.py --corpus-dir .local/amr --sector animal --title "Veterinary stewardship in Zambia" --query "radio programmes farmers traditional leaders Zambia" --query "AMR surveillance in poultry populations in Zambia" --confirm
```

### 检查检索效果

```bash
python scripts/check_amr_retrieval.py
python scripts/check_amr_retrieval.py --all-sectors
```

先为每个问题指定可支持答案的课件和页码，再核对前五个结果。此次 5 个英文问题在 70 份动物健康与 One Health 课件中全部找到预期原页；在全部 150 份中重跑也全部命中。下表给出两个范围中首个命中证据页的名次。该结果只衡量这五个问题的选页表现。

| 测试问题（中文摘要） | 首个证据页排名 | 原始页码 |
|---|---:|---:|
| 赞比亚家禽等动物的 AMR 监测政策 | 1 | 17 |
| 英国兽用抗菌药销售与动物群体规模 | 2 | 3 |
| 法国 Écoantibio 减少动物抗菌药暴露的目标 | 1 | 3 |
| 捷克 300 头奶牛农场初期的健康与管理问题 | 1 | 10 |
| 赞比亚如何向农户和传统领袖宣传合理用药 | 1 | 10 |

使用 `--language zh` 可把同样的测试意图换成中文，仍以相同的原始课件和页码评分。动物健康和 One Health 范围中，英文命中 5/5 个预期原页，中文命中 2/5。两组测试均使用本地检索器。[中英文逐项解释](../../../docs/AMR_SELECTION_LOGIC_CN.md)

## 爬虫怎样发现和复核新材料

```bash
python scripts/discover_amr_training.py --source all
```

爬虫从三个发布方的公开入口读取链接和资料记录。

| 来源 | 发现课件的路径 |
|---|---|
| 欧盟农户与兽医培训项目 | 读取课程资料页中的国家、场次和原始 PPTX 链接。同一文件在多场出现时合并。 |
| 英国兽药管理局 | 从 GOV.UK 的 UK-VARSS 发布集合进入各年度记录，核对附件的文件类型和官方地址。 |
| CGIAR 的 CGSpace | 按 AMR、AMU、抗菌药等英文词检索演示文稿记录，按标题筛选畜牧、农业、One Health 和用药管理等主题，再从记录中取出版方的原始 PPTX 附件。标题或主题词不在这些规则中的课件可能漏收。 |

2026 年 11 月 24 日实测得到 256 个课件链接。欧盟课程库有 234 个（32 个已收录、202 个待复核），英国年度材料有 7 个（均已收录），CGSpace 有 15 个（均已收录）。这 54 个已收录链接是完整目录的一部分。

每次扫描新建一个本地运行目录，终端会打印其路径。`report.json` 逐站记录请求次数、成功、空结果或失败。各站的清单分别保存，完整扫描另外生成合并的 `candidates.csv`。链接与已有目录比对，已经收录的标为 `listed`，其余标为 `candidate_unreviewed`。扫描中断时，运行 `python scripts/discover_amr_training.py --resume 上次运行目录` 会复用完整的站点清单，重试尚未完成的来源。省略 `--source` 可继续使用原有的欧盟单站扫描，输出兼容的 `.local/amr-training-candidates.csv`。

### 下载指定候选，核对原件是否重复

下面的例子从欧盟扫描结果中选择同一节课的英文和德文链接。多站扫描的 `candidates.csv` 也可以作为输入。

```bash
python scripts/discover_amr_training.py
python scripts/review_amr_candidates.py --candidates .local/amr-training-candidates.csv --url https://www.amrfvtraining.eu/wp-content/uploads/2025/02/03-L1_eng.pptx --url https://www.amrfvtraining.eu/wp-content/uploads/2025/02/03-L1_de_revised.pptx
```

复核程序实际下载指定的源文件、核对 PowerPoint 能否解析、统计原始页数，再将 SHA-256 与已收录目录及本批文件比对。实测两个版本各 22 页。英文版与目录原件完全一致，德文版的文件校验值不同；出版方的课程场次和标题显示两者是同一讲义的不同语言版本。`review.json` 保留逐项结论与失败原因。审核人仍需核对内容、翻译或近似版本、原始证据页和复用条款，然后决定是否入库。[下载复核代码](../../../scripts/review_amr_candidates.py)
