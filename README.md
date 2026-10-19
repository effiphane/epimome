# 虾铺开张中 — エピファネイア & エフフォーリア 産駒データベース

静态网站：`index.html` 读取 `data.js` 展示产驹数据（1473 匹）。

## 自动更新（GitHub Actions）

- `scrape_and_build.py` — 抓取 netkeiba → 生成 `data.js`
- `.github/workflows/update.yml` — 每周一自动运行抓取并提交
- Netlify 检测到提交后自动重新发布网站

## 本地运行

```bash
pip install requests beautifulsoup4
python scrape_and_build.py
```
