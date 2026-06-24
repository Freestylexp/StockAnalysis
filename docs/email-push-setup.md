# 邮件每日推送（GitHub Actions）

每个 **A 股交易日 17:00（北京时间）** 自动发送报告到你的邮箱。

## 一、准备 QQ 邮箱授权码（推荐）

1. 登录 [mail.qq.com](https://mail.qq.com)
2. **设置 → 账户**
3. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
4. 开启 **POP3/SMTP 服务** 或 **IMAP/SMTP 服务**
5. 按提示发短信，获得 **16 位授权码**（不是 QQ 登录密码）

默认 SMTP：

| 项目 | 值 |
|------|-----|
| SMTP_HOST | `smtp.qq.com` |
| SMTP_PORT | `465` |

Gmail 用户：`SMTP_HOST=smtp.gmail.com`，`SMTP_PORT=587`，需应用专用密码。

## 二、配置 GitHub Secrets

打开：**Settings → Secrets and variables → Actions**

| Secret | 必填 | 示例 |
|--------|------|------|
| `SMTP_USER` | ✅ | `you@qq.com` |
| `SMTP_PASSWORD` | ✅ | QQ 邮箱 16 位授权码 |
| `EMAIL_TO` | 可选 | 收件邮箱，不填则发给自己 |
| `SMTP_HOST` | 可选 | 默认 `smtp.qq.com` |
| `SMTP_PORT` | 可选 | 默认 `465` |
| `APP_URL` | 可选 | Hugging Face 网页链接 |

## 三、推送代码并测试

```bash
cd ~/Projects/stock-portfolio-agent
./scripts/setup-github-push.sh
```

GitHub → **Actions** → **Daily Email Report** → **Run workflow**

## 四、本地测试

```bash
export SMTP_USER='your@qq.com'
export SMTP_PASSWORD='你的授权码'
export EMAIL_TO='your@qq.com'   # 可选
./scripts/test-email-push.sh
```

## 五、邮件内容

- 正文：HTML 摘要（组合盈亏、持仓建议、买入参考）
- 附件：完整 Markdown 报告（生成成功时）

## 六、微信收邮件提醒

QQ 邮箱可绑定微信，新邮件会推送到微信。
