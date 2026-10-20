# -*- coding: utf-8 -*-
"""调试5：定位 runner 链接，dump 前后 HTML"""
import requests, re, json

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

r = requests.get('https://db.netkeiba.com/sire/thisweek/2010104155/', headers=HEADERS, timeout=30)
r.encoding = 'euc-jp'
html = r.text

out = {}
first_pos = None
for m in re.finditer(r'/horse/(\d+)/', html):
    hid = m.group(1)
    if hid not in ('2010104155', '2018105027'):
        if first_pos is None:
            first_pos = m.start()
        out.setdefault('runnerIDs', []).append(hid)

out['runnerIDs'] = list(dict.fromkeys(out.get('runnerIDs', [])))
if first_pos is not None:
    out['首个runner附近HTML'] = html[max(0, first_pos - 2500):first_pos + 3500]

with open('_thisweek_debug.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('done')
