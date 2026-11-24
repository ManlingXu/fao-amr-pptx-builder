# AMR 专题 PowerPoint 演示

[浏览 150 份课件及原始来源](catalog.csv) · [检索测试题](queries.csv) · [综合主题的 120 份演示库](../README.md)

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

候选结果列出课件标题与原始页码。在终端选择候选页、核对顺序，输入 `yes` 后生成本地初稿。`source_map.json` 记录各页的出处和校验值。同一组查询也可以用 `--confirm` 测试自动组装。初稿复制兼容的原始页，原来是图片的内容仍是图片。对外分享或改编前，按来源页核对授权和署名；`license` 为空表示未核实具体复用条款。仓库提供目录和代码，源课件按需从发布方下载。

### 复现赞比亚两页简报

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

### 发现后续新增课件

```bash
python scripts/discover_amr_training.py
```

本次扫描发现 234 个不同的 PPTX 链接，32 个已收录，另有 202 个待复核，其中包含同一课件的翻译和不同场次版本。脚本扫描欧盟项目的公开资料页，将课件链接与已收录目录比对，并保存到 `.local/amr-training-candidates.csv`。同一课件可能出现在多个国家场次，也可能另有翻译或轻微改版。未收录链接标为 `candidate_unreviewed`，经正文复核和去重后才能进入正式检索库。该命令可以手动重跑。
