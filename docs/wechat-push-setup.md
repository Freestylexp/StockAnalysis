# 微信每日推送（GitHub Actions + PushPlus）

每个 **A 股交易日 17:00（北京时间）** 自动生成报告并推送到微信。

## 一、注册 PushPlus

1. 打开 https://www.pushplus.plus
2. 微信扫码登录
3. 在「一对一推送」或「首页」复制 **Token**

## 二、推送代码到 GitHub

```bash
cd ~/Projects/stock-portfolio-agent
git add -A
git commit -m "Add GitHub Actions daily WeChat push"
git push -u origin main
```

若 push 失败，先完成 GitHub 认证（SSH 或 Personal Access Token）。

## 三、配置 GitHub Secrets

打开仓库：**Settings → Secrets and variables → Actions → New repository secret**

| Secret 名称 | 必填 | 说明 |
|-------------|------|------|
| `PUSHPLUS_TOKEN` | ✅ | PushPlus 的 Token |
| `APP_URL` | 可选 | 网页地址，如 Hugging Face Space 链接，会附在推送里 |
| `PUSHPLUS_TOPIC` | 可选 | 群组编码，仅推送到群时需要 |

## 四、手动测试

1. GitHub 仓库 → **Actions**
2. 左侧选 **Daily WeChat Report**
3. 点 **Run workflow** → **Run workflow**
4. 约 1–3 分钟后，微信应收到推送

## 五、推送时间说明

- 默认：**周一到周五 17:00 北京时间**（UTC 09:00）
- 对应 A 股收盘后复盘时段
- 要改时间：编辑 `.github/workflows/daily-report-wechat.yml` 里的 `cron`

常用 cron（UTC）：

| 北京时间 | cron |
|----------|------|
| 17:00 工作日 | `0 9 * * 1-5` |
| 08:30 工作日 | `30 0 * * 1-5` |
| 20:00 工作日 | `0 12 * * 1-5` |

## 六、本地试跑（可选）

```bash
cd ~/Projects/stock-portfolio-agent
source .venv/bin/activate
export PUSHPLUS_TOKEN="你的token"
export APP_URL="https://huggingface.co/spaces/Freestylexp/stock-portfolio-agent"
python scripts/daily_push.py
```

## 七、注意事项

1. **持仓数据**：以 GitHub 仓库里的 `data/portfolio.json` 为准；改持仓后需 commit 并 push
2. **行情数据**：GitHub 服务器在境外，A 股接口可能偶发失败，推送会使用备选数据源
3. **免费额度**：PushPlus 个人免费版一般够用；可在 PushPlus 查看每日限额

## 八、推送内容

微信收到的是 **摘要**：

- 组合盈亏 + 近 1/5 日变化
- 每只持仓一句话操作建议
- 今日买入参考 Top 5

完整 Markdown 报告会保存在 GitHub Actions 的 **Artifacts** 里（可下载）。
