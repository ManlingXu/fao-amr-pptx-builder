# Deploy to a CSI-approved host / 部署到 CSI 批准的服务器

## 中文

本代码包已经通过本地测试；真实 Azure、Entra、SharePoint 和 Teams 接入还需在组织租户验证。推荐先部署到 CSI 已批准的试用环境，确认费用和负责人。

### 方案 A：已有 Linux Azure App Service

1. CSI 准备专用 Linux Python 3.12 App Service（或兼容的 Python 3.11+ 版本）、支持 Always On 的方案、单实例及 HTTPS。此脚本不会新建订阅、资源组或收费方案。
2. 依据根目录 `.env.production.example`，在 App Service 的 Environment variables 中设置真实配置。应用使用 Entra 验证用户；Graph 服务身份须有指定源库读权限和输出位置写权限。令牌要使用 v2 格式。
3. 配置持久目录：`DRAFTS_PATH=/home/data/ppt-assistant/drafts`，`SHAREPOINT_CACHE_PATH=/home/data/ppt-assistant/sharepoint-cache`。不要放在部署代码目录。CSI 设置容量、保留期和备份安排。
4. 在已安装依赖的本地项目根目录运行：
   ```text
   python scripts/make_deploy_zip.py
   bash deploy/azure-appservice.sh RESOURCE_GROUP APP_NAME SUBSCRIPTION_ID
   ```
   替换三个参数。脚本检查已有应用及配置名称，设置 HTTPS、Always On、单进程启动和构建开关，再上传 `build/app-deploy.zip`。运行者需要该应用的部署及配置权限。
5. 确认 `https://APP_HOST/health`，随后使用真实用户连接器测试搜索、生成和 SharePoint 文件链接。健康检查不能代替权限及内容验收。

脚本会改动指定应用的部署和启动配置，并重新部署代码。请使用 CSI 指定的专用试用应用。它不会生成、打印或上传密钥文件；机密由 CSI 在平台中设置。部署文件已经排除 `.env`、运行数据和本地测试环境。

**运行范围：** 一台实例、一个 Uvicorn 进程。两个后台组装线程，最多十二个待处理／运行任务。重启后未完成任务标记失败；远程上传后发生崩溃时，先按 job ID 检查输出文件夹再重试。此版本没有跨实例队列和分布式锁。

### 方案 B：CSI 现有服务器 / Docker

CSI 可以在已有 Linux 主机上运行相同 Python 服务，外部提供 HTTPS，并允许访问 Entra 与 Microsoft Graph。直接运行时使用：
```text
python -m uvicorn presentation_search.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers
```
正式配置使用 Entra；不要把 `local_demo` 暴露到网络。宿主机上为运行用户提供持久可写目录。

附带的 `compose.yaml` 用于本机容器试用。先复制 `.env.example` 为 `.env`，设置非空且随机的 `COPILOT_API_KEY`，然后运行 `docker compose up --build`。它绑定本机端口，使用只读示例源目录和持久状态卷。组织容器部署需由 CSI 配置 Entra 环境变量、TLS 入口及持久卷；不要直接把本机 compose 当作组织部署完成。

## English

### Existing Azure App Service

CSI provisions an approved Linux Python 3.12 application (or compatible Python 3.11+ runtime), an Always On capable plan, one instance and HTTPS. Configure the real values from `.env.production.example` in App Service environment settings first. Use Entra user authentication and a separately authorized Graph application identity. Keep draft and cache paths under persistent `/home/data/ppt-assistant`.

From the project root, build `python scripts/make_deploy_zip.py`, then run:
```text
bash deploy/azure-appservice.sh RESOURCE_GROUP APP_NAME SUBSCRIPTION_ID
```
An optional fourth argument selects a different source ZIP. The script targets an existing app, checks configured setting names, enables HTTPS and Always On, sets a one-process startup command and build automation, and deploys source at the ZIP root. It does not provision a subscription or hosting plan. It changes the selected app's deployment/configuration, so use CSI's designated pilot app. Secrets remain in platform settings.

A successful public `/health` response is only the first check. Verify real-user authentication, source access, draft ownership, output-folder permissions and connector operation with CSI.

Use one instance and one service process. In-flight jobs fail on restart. A remote file may exist if the process stopped immediately after upload; its filename includes the unique job ID. CSI must set retention, capacity monitoring and maintenance ownership. This pilot does not implement a distributed queue.

### Existing host / Docker

An approved existing server can run the same Uvicorn command shown above with HTTPS in front, Entra configuration, outbound Microsoft connectivity and persistent writable paths.

The supplied Compose file is a localhost API-key trial. Copy `.env.example`, supply a nonblank random `COPILOT_API_KEY`, and run `docker compose up --build`. Source files are read-only; job state uses a named volume. CSI must adapt authentication, TLS and persistent mounts for organizational hosting.

## Microsoft documentation

- [Configure a Linux Python app, build automation and persistent paths](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python)
- [Deploy ZIP source to App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip)
- [Configure a Python startup command](https://learn.microsoft.com/en-us/azure/developer/python/configure-python-web-app-on-app-service)
