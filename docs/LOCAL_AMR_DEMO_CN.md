# Windows 本地 AMR 简报演示手册

从七份英国兽药监测年报中做一份十页简报，现场核对某一页的原始出处，再给同一份初稿换母版。第一次只需要 Windows、PowerShell、Python 3.11 或 3.12，以及安装依赖所需的网络。已有 PowerPoint 可以查看和编辑结果。整个演示无需 Microsoft 租户。

## 1 重启后从这里开始

**第一次解压。** 把交付的 AMR_Local_Demo.zip 放进“下载”。右键选择“全部解压”，目标选“下载”下的 AMR_Local_Demo。保留旧工程及其课件。以下各框每一行都是一条完整的 PowerShell 命令。一行复制一次，按 Enter，等上一条执行结束。

```powershell
$dl = Join-Path $env:USERPROFILE "Downloads"
$demo = Join-Path $dl "AMR_Local_Demo"
$found = Get-ChildItem $demo -Filter start-amr.cmd -File -Recurse
$start = $found | Select-Object -First 1
Set-Location $start.DirectoryName
Test-Path .\scripts\run_local_brief.py
```

最后一行应显示 True。没有找到文件时，在资源管理器中搜索 start-amr.cmd，打开它所在的文件夹，在地址栏输入 powershell 并回车。若从 GitHub 获取源码，应下载含此启动文件的版本，将新解压的工程命名为 amr-workbench。系统可能同时存在多个名为 fao-amr-pptx-builder-main 的文件夹，应用启动文件确认版本。

**第一次启动英国案例。** 下列启动器会创建虚拟环境并安装项目。保留这个 PowerShell 窗口，在浏览器地址栏打开 http://127.0.0.1:8765 。

```powershell
.\start-amr.cmd "..\UK_Example"
```

看到命令行提示 Python 版本有问题时，先运行下一条。若仅列出 3.10，安装 Windows 版 Python 3.12，关闭并重新打开 PowerShell，然后从本页第一条命令开始。

```powershell
py -0p
```

下次开机仍可逐行执行本页命令。无需重复解压。关闭网页不会关闭服务，在运行服务的窗口按 Ctrl+C 即可停止。Python 下载入口 https://www.python.org/downloads/windows/

<!-- page -->

## 2 当场生成十页并换模板

**选一个有材料的主题。** 使用随包 UK_Example 时，将网页“主题”替换为下面的英文原文，目标页数填 10，选择“动物健康”。先把“本地 Ollama 模型”和模板都留空，点击“生成 PowerPoint 初稿”。

```text
UK veterinary antibiotic sales and resistance surveillance
```

**看它选了什么。** 右侧会显示实际选入的页数、原课件标题、原页码、匹配的文字和“打开来源”。先点击一页的来源，再点“下载初稿”和“下载模板版”。在 PowerPoint 中打开 draft.pptx，选择底部“备注”查看该页引用的出版者、原页码、网址和 SHA-256。网页返回不足十页时，实际数量和缺口会直接显示。

**比较两种设计。** 把 draft.pptx 和 styled.pptx 停在同一页。在模板版中指出母版背景、页边或标题位置的变化，在备注区确认原页码和链接仍相同。若希望每页按统一结构重排，可在生成时勾选“统一编排证据页”，程序会重排可核验的原文；跨源页面不兼容时也会使用这种版式。

**把同一份初稿换成自己的模板。** 在结果区“为这份初稿更换模板”选择一个含母版设计的 .pptx 或 .potx，点击“应用新模板”再点“下载新模板版”。此按钮只使用本次已生成的 draft.pptx，无需重新检索。保留初稿即可重复试用多套模板；重启浏览器会话后，可以用第 5 节的命令为已有文件换版。

**还没有自己的模板时。** 用 PowerPoint 新建空白演示，打开“视图 → 幻灯片母版”，选左边最上方的大母版，设置浅色背景，并在右边缘加一条彩色竖线。关闭母版视图，另存为“下载”下的 My_AMR_Template.pptx，再按上一步上传。图形放在母版上，普通示例页上的图形不会作为模板装饰导入。文件上限 16 MiB。

**只看成品时。** 压缩包中的 Example_Outputs 包含预生成的英国案例。首次安装依赖尚未完成，也可以先打开初稿与模板版，在 PowerPoint 中并排查看同一页。

**讲解时可以这样说。** “我点开这条来源，能回到原机构发布页，还能在备注找到原始页码。现在我锁定这份十页初稿，更换的是发布样式。请看同一页的设计和出处。”

<!-- page -->

## 3 复用旧课件或下载完整材料

**找回原来下载的资料。** 在刚才运行服务的窗口先按 Ctrl+C。继续在新工程目录中执行以下命令。第一行里的路径对应你之前的运行记录。它也适用于包含中文的 Windows 用户名。

```powershell
$old = Join-Path $env:USERPROFILE "Downloads\fao-amr-pptx-builder-main\.local\amr"
Test-Path "$old\verified.csv"
(Import-Csv "$old\verified.csv").Count
Invoke-Item "$old\presentations"
```

True 表示找到已校验清单；随后会显示实际课件数并打开原 PPTX 目录。上次控制台显示的 67 份、1,355 页对应那一次已索引的材料。用旧资料演示赞比亚案例时，运行下一条，再打开同一网页，主题改为“赞比亚兽医抗菌药物管理、国家行动计划、养殖户培训和动物监测”，选 10 页，勾选“动物健康”和“One Health”。

```powershell
.\start-amr.cmd "$old"
```

**在新版工程建完整资料库。** 按 Ctrl+C 停止服务，再逐行执行。下载器默认读取项目自带目录，建在新版工程的 .local\amr。下载与原文件核验需要网络。网站日后可能修改或移除文件，实际数量以本机 report.json 为准。

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\fetch_public_corpus.py --corpus-dir .local\amr --workers 4
Get-Content .local\amr\report.json -Raw
.\start-amr.cmd ".local\amr"
```

此版目录收录 184 份、4,708 页、31 个来源网站。整库实测下载并校验 183 份、4,697 页；其中一份 BSAC 人医课件返回了网页，未通过文件校验。随包的英国小样本含七份 UK-VARSS 年报，可独立使用。

**文件如何对应。** examples\public_corpus\amr\catalog.csv 保存机构、作者、年份、领域、语种、主题、许可、发布页和下载地址等字段。.local\amr\verified.csv 是本机核验成功的文件清单。用其中的 id 对应 presentations\<id>.pptx，用 sha256 确认文件版本，slide_count 是原课件页数。

<!-- page -->

## 4 向观众解释检索和 AI

**Python 怎样挑页。** 程序逐页索引标题、正文、表格文字和演讲者备注，用领域词表把“赞比亚”“养殖户”“用药管理”等词与英文表达对应。检索会检查地域和领域、比较页内证据、去重并适度分散来源。同一份课件按原稿顺序呈现，多份课件按背景、政策、实施、监测、下一步组织。它会报告资料不足，便于你调整主题或补充来源。

**给每一页留证据。** 默认优先保留兼容源页的可编辑对象；摘录排版会保留有出处的文本，可带同页主图或小型表格。图像选择依据同页、尺寸与裁剪等条件，当前流程没有自动解读照片含义或图表趋势。请在讲到具体数值时回到原图核对单位、年份和对象。

**启用可下载的本地模型。** 如果之前装过 Ollama，先运行第一条；列表中已有 qwen3:4b 时可直接使用。未安装 Ollama 时，先安装 Windows 客户端并打开；列表里没有该模型时再运行第二条。安装与首次拉取需要网络。模型下载约 2.5 GB。可在另一个 PowerShell 窗口执行，不影响正在运行的工作台。

```powershell
ollama list
ollama pull qwen3:4b
```

在网页“模型与模板 → 本地 Ollama 模型”填 qwen3:4b，以相同主题和页数重新生成一份。模型从真实候选页及原文片段中挑选，返回页 ID 和证据片段；Python 校验后负责排序、保存归属和生成文件。对比两份结果中原页码、相关证据、重复程度和资料缺口。每次运行的 summary.json 用 llm_called 和 model_used 记录是否实际调用模型。选了模型但连接失败时，界面会提示错误。

**日后接入 Copilot Studio。** 可以让代理先澄清受众和重点，拆成章节，再调用检索与导出工具。Python API 提供可调用的搜索和导出动作，Custom connector 将动作名、参数、身份验证方式登记给 Copilot；Azure 可以托管后端。租户中仍需配置连接和权限。检索准确性应在同一套有标准答案的题目上比较，再判断提升幅度。

参考文档 https://docs.ollama.com/windows · https://ollama.com/library/qwen3:4b · https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-tools-custom-agent

<!-- page -->

## 5 用命令复演并发现新课件

**从终端生成十页。** 在 amr-workbench 工程目录执行下列命令。这里使用随包英国素材。指定 --reflow 会把选中页重排为统一的证据摘录；去掉它则优先保留兼容原页。

```powershell
$py = ".\.venv\Scripts\python.exe"
$src = "..\UK_Example"
$q = "UK veterinary antibiotic sales and resistance surveillance"
& $py scripts\run_local_brief.py --corpus-dir $src --topic $q --pages 10 --reflow
$runs = Get-ChildItem build\amr-briefs -Directory -Filter "brief-*"
$r = $runs | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

**给已有初稿换模板。** 先按第 2 节把模板保存到“下载”。运行下列命令可在原输出目录另存一份新设计。末行打开目录，里面的 source_map.json 按输出页序记录原文件、原页、网址、作者、证据和校验值。若重复换版，换一个输出名。

```powershell
$t = Join-Path $env:USERPROFILE "Downloads\My_AMR_Template.pptx"
$draft = Join-Path $r.FullName "draft.pptx"
$copy = Join-Path $r.FullName "my-template.pptx"
& $py scripts\run_local_brief.py restyle --draft $draft --template $t --output $copy
Invoke-Item $r.FullName
```

**扫描机构网站的新链接。** 下列命令沿七组机构站点查找课件，包括欧盟农户及兽医培训、英国 UK-VARSS、CGIAR、RCGP TARGET、瑞典 Strama、欧委会宣传资料和英国 e-Bug。每次保存一个独立扫描目录。listed 表示已列入目录，candidate_unreviewed 需要复核。

```powershell
& $py scripts\discover_amr_training.py --source all
```

**下载一份候选供审查。** 将扫描结果输出的 candidates.csv 完整路径和要复核的那行 download_url 分别粘贴到以下两次提示中。review.json 记录哈希、页数和查重结果；核对机构、原文、许可和代表页后，再维护目录。单纯扫描不会扩大工作台的可搜索课件数。

```powershell
$csv = Read-Host "Paste full candidates.csv path"
$url = Read-Host "Paste exact download_url"
& $py scripts\review_amr_candidates.py --candidates $csv --url $url
```
