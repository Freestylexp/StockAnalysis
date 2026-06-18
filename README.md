---
title: A股持仓分析
emoji: 📈
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.32.0
app_file: app.py
pinned: false
---

# A股持仓分析

网页版 A 股持仓分析工具：管理持仓和关注股，查看价格走势，生成盈利导向的买卖建议。

## 在线访问（Hugging Face）

部署完成后，Space 地址形如：

**https://huggingface.co/spaces/你的用户名/stock-portfolio-agent**

手机浏览器或微信内均可打开该链接（建议收藏到微信「文件传输助手」）。

> 云端运行在境外服务器，A 股行情接口可能偶发失败；在 Space 里修改的持仓在重启后可能恢复为仓库默认数据。

---

## 本地启动

```bash
cd ~/Projects/stock-portfolio-agent
chmod +x start.sh
./start.sh
```

浏览器打开 **http://127.0.0.1:8501**

或手动：

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 127.0.0.1
```

## 功能

| 页面 | 功能 |
|------|------|
| **总览** | 持仓市值、浮动盈亏、操作建议速览 |
| **价格走势** | K 线、均线、盈利目标线 |
| **搜索股票** | 代码/名称搜索，加入持仓或关注 |
| **持仓管理** | 添加/更新/删除持仓 |
| **关注股** | 管理观察列表 |
| **每日分析** | 一键生成报告，含操作建议和新股推荐 |
| **个股速查** | 输入代码即时分析 |

## 部署到 Hugging Face Spaces（免费）

### 1. 把代码推到 GitHub

```bash
cd ~/Projects/stock-portfolio-agent
git add -A
git commit -m "Add Streamlit app and Hugging Face Spaces config"
git push -u origin main
```

若 push 失败，先在 GitHub 创建空仓库，或用 [GitHub CLI](https://cli.github.com/) 登录：`gh auth login`

### 2. 创建 Space

1. 打开 [huggingface.co/new-space](https://huggingface.co/new-space)
2. **Space name**：`stock-portfolio-agent`（可自定）
3. **License**：MIT
4. **SDK**：Streamlit
5. **Hardware**：CPU basic（免费）
6. **Visibility**：Private（仅自己可见，推荐）或 Public

### 3. 连接 GitHub 仓库

在 Space 页面 → **Settings** → **Repository** → 选择 `Freestylexp/StockAnalysis`（或你的仓库）→ 保存。

HF 会自动读取本仓库根目录 `README.md` 顶部的 YAML 配置并部署。

### 4. 等待构建

**Logs** 标签页显示 `Running` 后即可访问。首次构建约 2–5 分钟。

### 5. 手机 / 微信使用

- 复制 Space 的 **App** 链接
- 发到微信「文件传输助手」并收藏
- 或在浏览器中打开后「添加到主屏幕」

---

## 数据说明

| 环境 | 持仓数据 |
|------|----------|
| 本地 | 保存在 `data/portfolio.json` |
| Hugging Face | 默认读取仓库内 `data/portfolio.json`；网页中的修改在 Space **重启/重新部署** 后会丢失 |

要长期保存云端持仓，需后续接入数据库（如 Supabase 免费版）。

## 命令行（可选）

```bash
python main.py list
python main.py analyze --save
```

## 免责声明

本工具仅供参考，不构成投资建议。股市有风险，投资需谨慎。
