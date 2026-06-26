# 邮件每日推送（GitHub Actions）

每个 **A 股交易日 12:00 左右（北京时间）** 自动发送报告到你的邮箱。

> **无需电脑开机**：任务在 GitHub 云端运行，你的 Mac 关机也能收到邮件。

---

## 重要：为什么 GitHub 上 QQ SMTP 会失败？

本地 `./scripts/test-email-push.sh` 用 QQ SMTP 可以成功，但 **GitHub Actions 云端通常无法直连 `smtp.qq.com:465/587`**，会出现：

```
SMTPServerDisconnected: please run connect() first
```

这是云端网络对 SMTP 端口的限制，**不是授权码配错**。

**解决方案：** GitHub 自动推送请用 **Resend API（HTTPS）**；本地测试仍可用 QQ SMTP。

---

## 方案 A：Resend API（GitHub 自动推送，推荐）

### 1. 注册 Resend

1. 打开 https://resend.com 注册（建议用你要收报告的邮箱，如 QQ 邮箱）
2. 进入 **API Keys** → **Create API Key** → 复制 `re_...` 开头的密钥

免费版说明：

- 默认发件地址：`onboarding@resend.dev`
- 未绑定域名时，**只能发到 Resend 注册时用的那个邮箱**
- 每月约 3000 封，足够每日报告

### 2. 配置 GitHub Secrets

仓库 → **Settings → Secrets and variables → Actions**

| Secret | 必填 | 说明 |
|--------|------|------|
| `RESEND_API_KEY` | ✅ | Resend 的 `re_...` API Key |
| `EMAIL_TO` | ✅ | 收件邮箱（须与 Resend 注册邮箱一致，除非已绑域名） |
| `RESEND_FROM` | 可选 | 默认 `onboarding@resend.dev` |
| `APP_URL` | 可选 | Hugging Face 网页链接 |

### 3. 推送代码并测试

```bash
cd ~/Projects/stock-portfolio-agent
./scripts/setup-github-push.sh
```

GitHub → **Actions** → **Daily Email Report** → **Run workflow**

成功日志示例：

```
→ 方式：resend
→ 发件：onboarding@resend.dev  收件：your@qq.com
✅ 邮件发送成功
```

---

## 方案 B：QQ SMTP（仅适合本地）

本地终端：

```bash
export SMTP_USER='your@qq.com'
export SMTP_PASSWORD='你的16位授权码'
export EMAIL_TO='your@qq.com'
./scripts/test-email-push.sh
```

QQ 授权码：QQ 邮箱 → 设置 → 账户 → 开启 POP3/SMTP → 生成授权码。

**不要把 SMTP 当作 GitHub 自动推送方案**，云端大概率连不上。

---

## 定时规则

`.github/workflows/daily-report-email.yml`：

```yaml
cron: "0 4 * * 1-5"   # UTC 04:00 = 北京时间 12:00，周一至周五
```

GitHub 可能延迟 0–15 分钟触发。

---

## 邮件内容

- 正文：HTML 摘要（组合盈亏、持仓建议、**关注股动向**、买入参考）
- 附件：完整 Markdown 报告（生成成功时）

QQ 邮箱可绑定微信，新邮件会推送到微信。

---

## 故障排查

| 现象 | 处理 |
|------|------|
| `please run connect() first` | 改用 **RESEND_API_KEY**，不要用 SMTP |
| `Resend API 失败 (403)` | `EMAIL_TO` 须是 Resend 注册邮箱，或绑定发信域名 |
| `invalid literal for int()` | 删除空的 `SMTP_PORT` Secret（云端已不需要 SMTP） |
| 本地能发、Actions 不能发 | 正常；本地 SMTP / 云端 Resend 两套配置 |
