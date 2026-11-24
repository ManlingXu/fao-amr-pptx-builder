# Public PowerPoint demo

**AMR 专题演示**可检索 150 份原始课件，并单独筛选动物健康及 One Health 资料。[专题目录与运行步骤](amr/README.md)

[下载实测样例 · Download the worked example](Vietnam_AMR_demo.zip) · [查看 120 份来源 · Browse the catalogue](catalog.csv)

原版有 4 份合成课件、6 页。本演示使用 120 份不同的公开 PowerPoint，共 2,322 页，原始文件约 579 MB。113 份来自 CGIAR 的 CGSpace，涉及 AMR、One Health、食品安全、畜牧业和生计。另有 7 份英国兽药管理局的年度监测报告，覆盖 2019–2025 报告年。按标题统计，18 份直接提到抗微生物药物或抗生素。所有课件均已下载、按内容去重、核对 SHA-256 并用项目的实际解析器建立索引。

## 看一个真实结果

演示任务是为兽医公共卫生同事准备一个短报告。先介绍越南的 AMR 研究重点，再讲太原省的兽用抗菌药管理，最后用一页说明如何沟通风险。系统先拟定章节，再调整顺序。确认后，导出的 PPT 保留原页中的可编辑文字。压缩包内附逐页出处和作者署名。两份原始报告均出版于 2019 年。

| 初稿页码 | 选中的内容 | 原始课件与页码 |
|---|---|---|
| 1 | 越南的 AMR 与抗微生物药物使用研究重点 | [越南农业食品体系 AMR/AMU 研究](https://cgspace.cgiar.org/items/f8b9bbe5-22ec-4a2d-90e6-2599f1fdb0c5)，第 5 页 |
| 2 | 太原省兼顾农户生计的兽用抗微生物药物管理 | 同一课件，第 9 页 |
| 3 | 将研究用于风险沟通与管理 | [发展中国家的 One Health 与食品安全研究](https://cgspace.cgiar.org/items/a8ecb669-c44e-44d4-bf0b-335aa50da5f4)，第 41 页 |

## 自己选页

在项目根目录使用 Python 3.11 或 3.12。以下命令以已激活的虚拟环境为例。首次运行需要联网下载，之后可使用本地缓存。

```bash
python -m pip install -e ".[test]"
python scripts/fetch_public_corpus.py
python scripts/run_public_corpus_demo.py --query "antimicrobial resistance" --query "One Health" --interactive
```

每个主题最多显示 15 个候选页。输入编号可以换页，用逗号指定顺序。回车接受建议，最后输入 `yes` 才会导出本次选择。添加 `--reverse-sections` 可以在修订时反转章节顺序，添加 `--template path/to/design.pptx` 可以试用自己的模板。下载报告在 `.local/public-corpus/report.json`。每次演示会在 `build/public-corpus-demo/` 下新建一个结果目录，保留检索结果、版本、两版大纲和导出记录。

## Reproduce the worked example

After installing the project and fetching the catalogue, run the following command on one line. It uses the project's local search, version, plan, revision and draft APIs. The three supplied queries stand in for the sections that a configured Copilot agent would propose.

```bash
python scripts/run_public_corpus_demo.py --title "Vietnam AMR research, veterinary stewardship and risk communication" --query "Risk communication and management" --query "livelihood-sensitive veterinary AM stewardship in Thai Nguyen" --query "Key areas of AMR/AMU research in Vietnam" --reverse-sections --confirm
```

To inspect reporting years, try `--query "Antibiotic Usage Data"` in a separate run and open `versions.json`. In the full-corpus run the first hit's version group included slides from all seven [UK VARSS annual presentations](https://www.gov.uk/government/collections/veterinary-antimicrobial-resistance-and-sales-surveillance). Version matching uses slide-title and filename heuristics. The source publication date and the reporting period inferred from the slide are separate fields.

- `--limit 10` on the fetch command gives a smaller first download. Run the fetch command without a limit to use all 120 again. The demo uses only the files in the current `verified.csv`.
- Without `--interactive` or `--confirm`, the demo saves a plan for inspection. `--confirm` approves the scripted revision for that run. The output directory is printed when the run finishes.
- Native slide assembly checks canvas size, default text styles, notes masters and embedded content. The scripted path tries compatible candidates and records rejected selections. If it cannot fill a section, it reports the gap. Use interactive review to choose the strongest content match.
- The CSV records the public source page, download URL, author, publication date, licence and SHA-256 of each verified file. Keep the credits with any shared extract. Original decks are downloaded on demand. A changed file or unavailable host appears in the download report. Rerunning reuses successful downloads.
- This simulation runs locally without Microsoft credentials, an LLM or a SharePoint connection. Live Teams conversation and tenant file delivery still depend on the [Copilot Studio setup](../../docs/COPILOT_STUDIO_EN.md).
