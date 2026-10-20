# -*- coding: utf-8 -*-
"""调试：dump netkeiba 本周出马页面结构"""
import requests, json
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.encoding = 'euc-jp'
    return r


out = {}
for label, sid in [('Epiphaneia', '2010104155'), ('Efforia', '2018105027')]:
    r = fetch(f'https://db.netkeiba.com/sire/thisweek/{sid}/')
    soup = BeautifulSoup(r.text, 'html.parser')
    info = {'标题': soup.title.get_text(strip=True) if soup.title else ''}
    for ti, t in enumerate(soup.find_all('table')):
        rows = t.find_all('tr')
        if not rows:
            continue
        hdr = ' '.join(c.get_text(strip=True) for c in rows[0].find_all(['td', 'th']))
        sample = [[c.get_text(strip=True) for c in tr.find_all(['td', 'th'])] for tr in rows[1:4]]
        info[f'表{ti}'] = {'表头': hdr[:250], '行数': len(rows), '样例3行': sample}
    links = []
    for a in soup.find_all('a', href=True):
        t = a.get_text(strip=True)
        if t:
            links.append({'文字': t[:25], 'href': a['href'][:60]})
    info['链接'] = links[:40]
    out[label] = info

with open('_thisweek_debug.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('done')
