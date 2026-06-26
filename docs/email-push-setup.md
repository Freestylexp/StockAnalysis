# 邮件每日推送（GitHub Actions）

每个 **A 股交易日 12:00 左右（北京时间）** 自动发送报告到你的邮箱。

> **无需电脑开机**：任务在 GitHub 云端运行，你的 Mac 关机也能收到邮件。

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

## 二、配置 GitHub Secrets（自动推送必做）

打开仓库：**Settings → Secrets and variables → Actions → New repository secret**

| Secret | 必填 | 说明 |
|--------|------|------|
| `SMTP_USER` | ✅ | 发件 QQ 邮箱，如 `your@qq.com` |
| `SMTP_PASSWORD` | ✅ | QQ 邮箱 **16 位授权码**（不是登录密码） |
| `EMAIL_TO` | 建议填 | 收件邮箱；不填则发到 `SMTP_USER` |
| `SMTP_HOST` | 可选 | 默认 `smtp.qq.com` |
| `SMTP_PORT` | 可选 | 默认 `465` |
| `APP_URL` | 可选 | Hugging Face 网页链接 |

**本地测试能发邮件 ≠ 云端能发**：本地用的是终端里的环境变量；GitHub Actions 只读 Secrets，两者需分别配置。

### 确认 Actions 已开启

仓库 **Settings → Actions → General** → 选择 **Allow all actions**（或至少允许本仓库 workflow）。

### 确认定时任务在跑

**Actions** 标签页应能看到 **Daily Email Report**。若长期无运行记录，检查：

1. 上述 Secrets 是否都已保存（名称大小写必须一致）
2. 默认分支是否为 `main`，且 workflow 文件已在该分支
3. 私有仓库长期无活动，GitHub 可能暂停 schedule（手动 Run workflow 一次可恢复）

## 三、推送代码并测试

```bash
cd ~/Projects/stock-portfolio-agent
./scripts/setup-github-push.sh
```

1. GitHub → **Actions** → **Daily Email Report** → **Run workflow**（立即测试）
2. 查看本次运行日志，应出现 `邮件发送成功`
3. 检查邮箱（含垃圾箱）

定时规则：**周一至周五 12:00 北京时间**（UTC 04:00），GitHub 可能晚几分钟触发。

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
