# Hugging Face 与 GitHub 自动同步（方法 B）

> Hugging Face Space **Settings 里可能没有 Repository 按钮**（界面已调整，Docker Space 尤其常见）。  
> **推荐做法：** 用 GitHub Actions，push 到 GitHub 后**自动同步到 HF**——效果和「绑定 GitHub」一样。

---

## 一次性设置

### 1. 获取 Hugging Face Token

1. 打开 https://huggingface.co/settings/tokens  
2. **Create new token** → 类型选 **Write**  
3. 复制 `hf_...` 密钥

### 2. 添加到 GitHub Secrets

仓库 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|-------|
| `HF_TOKEN` | 刚复制的 `hf_...` |

（与邮件用的 `RESEND_API_KEY` 放在同一页即可。）

### 3. 推送含 workflow 的代码

```bash
cd ~/Projects/stock-portfolio-agent
./scripts/setup-github-push.sh
```

推送成功后，GitHub 会自动跑 **Sync to Hugging Face** workflow。

### 4. 验证

1. **Actions** → **Sync to Hugging Face** → 应显示绿色 ✅  
2. 打开 Space **Logs**，等待 **Running**  
3. 刷新 App，持仓与 GitHub 一致

验证 GitHub 数据：  
https://github.com/Freestylexp/StockAnalysis/blob/main/data/portfolio.json

---

## 以后怎么改持仓

```bash
# 本地改完持仓后，一条命令：
./scripts/sync-portfolio.sh
```

会自动：

1. push 到 GitHub  
2. 触发 **Sync to Hugging Face** → 更新手机网页  
3. 邮件仍读 GitHub 上的 `portfolio.json`（定时或手动 Run workflow）

等 HF **2–5 分钟**重建后刷新手机页面。

---

## 在 HF 设置里找不到 Repository？

常见原因：

| 情况 | 说明 |
|------|------|
| 界面改版 | 很多 Space 不再显示「Connect GitHub」 |
| Docker Space | 早期用 `deploy-hf.sh` 创建的，设置项更少 |
| 需新建 Space 时选 | 「Create from GitHub repo」才有仓库绑定 |

**不影响使用。** 本项目的 `.github/workflows/sync-huggingface.yml` 是 Hugging Face 官方推荐的同步方式。

---

## 还需要 `deploy-hf.sh` 吗？

配置好 `HF_TOKEN` 并 push 后，**一般不需要**。

仅当 Actions 同步失败时，可临时手动：

```bash
./scripts/deploy-hf.sh
```

---

## 数据流

```
本地改 portfolio.json
        ↓
./scripts/sync-portfolio.sh  →  GitHub (main)
        ↓                          ↓
  Sync to Hugging Face      Daily Email Report
        ↓                          ↓
   手机 HF 网页                   邮箱日报
```

---

## 故障排查

| 问题 | 处理 |
|------|------|
| Sync workflow 失败 | 检查 `HF_TOKEN` 是否有 Write 权限 |
| HF 仍是旧数据 | Actions 看 Sync 是否成功；Space → **Factory rebuild** |
| 邮件对了 HF 不对 | 确认 Sync workflow 跑过，不是只 push 了本地没 push GitHub |
