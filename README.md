# Periodicals R2 Sync

把指定 GitHub 仓库里的外刊同步到 Cloudflare R2，或安全下载到 Mac 本地原件资料库。

本项目默认同步：

- The Economist
- The New Yorker

来源仓库：

- https://github.com/ChrisWu12/awesome-english-ebooks

## 安全边界

- 不读取、不修改、不删除本地 Obsidian Vault 中的任何既有文件。
- GitHub Actions 只上传新对象到 Cloudflare R2。
- 脚本不会删除 R2 上的任何对象。
- 输出目录固定在 R2 的 `外刊/` 前缀下。
- 本机下载脚本只写入 Mac 本地原件资料库，不写入 Obsidian Vault。
- Obsidian Vault 只保存处理后的中英对照 Markdown 学习笔记。
- 如果你已经用 Möbius Sync 同步主 Vault，不建议再用 Remotely Save 管理同一个 Vault。

## R2 准备

在 Cloudflare R2 创建一个 bucket，例如：

```text
obsidian-periodicals
```

然后创建一个 R2 API Token，权限建议仅限这个 bucket：

- Object Read
- Object Write

不要授予删除权限，除非你明确需要。

Cloudflare R2 的 S3 endpoint 通常长这样：

```text
https://<account_id>.r2.cloudflarestorage.com
```

## GitHub Secrets

在你准备用来跑 Actions 的 GitHub 仓库里添加这些 Secrets：

```text
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
```

如果你想显式指定 endpoint，也可以加：

```text
R2_ENDPOINT_URL
```

不填 `R2_ENDPOINT_URL` 时，workflow 会自动使用：

```text
https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com
```

可选变量：

```text
GH_TOKEN
```

如果 GitHub API 频率限制较紧，可以填一个 GitHub token；公开仓库通常不必。

## 目录结果

R2 中会生成：

```text
外刊/
  The Economist/
    2026-08-08/
      The Economist 2026-08-08.md
      TheEconomist.2026.08.08.pdf
      TheEconomist.2026.08.08.epub
  The New Yorker/
    2026-08-10/
      The New Yorker 2026-08-10.md
      new_yorker.2026.08.10.pdf
      new_yorker.2026.08.10.epub
```

## 本地测试

只做干跑，不上传：

```bash
python3 scripts/sync_periodicals.py --config periodicals.json --dry-run
```

只预览最近 1 期，不上传：

```bash
python3 scripts/sync_periodicals.py --config periodicals.json --recent 1 --dry-run
```

真实上传最近 1 期：

```bash
python3 scripts/sync_periodicals.py --config periodicals.json --recent 1
```

## 下载到 Mac 本地原件库

推荐学习流：

```text
GitHub source repo
→ Mac 定期下载 PDF/EPUB 到本地原件库
→ Codex 读取本地原件并生成中英对照 Markdown
→ 处理后的 Markdown 放入 Obsidian Vault/外刊学习
→ Möbius Sync 只同步轻量 Markdown 到手机
→ Codex 按期刊/文章生成中英对照学习笔记
```

不要让 Remotely Save 和 Möbius Sync 同时同步同一个主 Vault。

默认原件库：

```text
/Users/chris/Documents/Periodicals Library/
```

只预览将写入哪些本地资料库文件，不下载：

```bash
python3 scripts/download_originals_to_library.py --config periodicals.json --recent 1 --dry-run
```

真实下载最近 1 期到本地资料库：

```bash
python3 scripts/download_originals_to_library.py --config periodicals.json --recent 1
```

旧版脚本仍保留，但不再推荐用于定时任务：

```bash
python3 scripts/download_to_vault.py --config periodicals.json --recent 1 --dry-run
```

## Obsidian 学习笔记目录

处理后的中英对照 Markdown 放在：

```text
/Users/chris/Desktop/Obsidian Vault/外刊学习/
  The Economist/
    2026-08-15/
      00 Issue Index.md
      03 The Taliban are vile. Democracies must still engage with them bilingual.md
```

`00 Issue Index.md` 会从本地 EPUB 自动生成编号目录，包含：

- 文章编号
- 文章标题
- 目标双语笔记文件名
- EPUB 内部来源文件

处理时可以直接说：

```text
处理 The Economist 2026-08-15 编号 01, 03, 05
```

生成的双语笔记文件名也应保留编号，例如：

```text
03 The Taliban are vile. Democracies must still engage with them bilingual.md
```

安全规则：

- 自动下载原件只写入 `/Users/chris/Documents/Periodicals Library/`
- Obsidian 只保存处理后的 Markdown
- 不删除任何文件
- 不覆盖已存在文件
- 不修改 `.obsidian`
- 不修改 Travel、Dairy、Templates 或其他已有目录

## 本机定时任务

已提供 macOS launchd 配置：

```text
launchd/com.chris.periodicals-download.plist
```

安装后会每周日本机时间 10:15 运行：

```bash
scripts/run_local_download.sh
```

该任务每次检查最近 6 期，补齐本地原件库缺失文件，并刷新 Obsidian 中的编号目录。

如果当次运行时没有网络，任务会失败并记录到错误日志；由于下一次会继续检查最近 6 期，通常会自动补齐漏掉的周刊。

安全规则：

- 只写入 `/Users/chris/Documents/Periodicals Library/`
- 不删除
- 不覆盖

日志位置：

```text
logs/local-download.out.log
logs/local-download.err.log
```

## GitHub Actions

workflow 文件在：

```text
.github/workflows/sync-periodicals.yml
```

它支持：

- 手动运行
- 每周五、周六定时运行
- 默认每种期刊只检查最近 2 期

## Obsidian 设置建议

如果你已经用 Möbius Sync 同步 Obsidian 主 Vault，不建议在同一个 Vault 上启用 Remotely Save。

更安全的方式是让本机下载脚本把外刊写入 `外刊/`，再由 Möbius Sync 负责同步到手机。

如果仍要使用 Remotely Save，请先在测试 Vault 里验证，并确认没有打开危险的清理/删除策略。目标是：

- 远端新增文件可以同步到本地
- 本地既有文件不会被删除
- Vault 现有目录不被自动清理

本项目输出的唯一目标目录是：

```text
外刊/
```
