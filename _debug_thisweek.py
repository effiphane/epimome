# -*- coding: utf-8 -*-
"""调试4：dump 本周出马 runner 区块的原始 HTML"""
import requests, re, json

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

r = requests.get('https://db.netkeiba.com/sire/thisweek/2010104155/', headers=HEADERS, timeout=30)
r.encoding = 'euc-jp'
html = r.text
out = {'HTML总长': len(html)}
idx = html.find('出走情報')
if idx >= 0:
    out['附近HTML'] = html[max(0, idx - 300):idx + 6000]
# runner 马匹ID（排除种马自己的 id）
runner_ids = []
for m in re.finditer(r'/horse/(\d+)/', html):
    hid = m.group(1)
    if hid not in ('2010104155', '2018105027'):
        runner_ids.append(hid)
out['runner马匹ID'] = list(dict.fromkeys(runner_ids))

with open('_thisweek_debug.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('done')
