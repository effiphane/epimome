# -*- coding: utf-8 -*-
"""调试：dump race.netkeiba.com 赛事页结构，找级别/等级"""
import requests, json
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.encoding = r.apparent_encoding
    return r


out = {}
for label, rid in [('東京4R新馬', '202605040604'), ('東京12R甲斐路S', '202605040612')]:
    r = fetch(f'https://race.netkeiba.com/race/result.html?race_id={rid}')
    soup = BeautifulSoup(r.text, 'html.parser')
    info = {}
    info['标题'] = soup.title.get_text(strip=True) if soup.title else ''
    txt = soup.get_text(' ', strip=True)
    for kw in ['条件', 'オープン', '新馬', '未勝利', 'クラス', 'リステッド', '重賞', 'GIII', 'GII', 'GI', 'サラ系', '1勝', '2勝', '3勝', 'グレード']:
        idx = txt.find(kw)
        if idx >= 0:
            info['含_' + kw] = txt[max(0, idx - 25):idx + 25]
    h1 = soup.find('h1')
    info['h1'] = h1.get_text(strip=True) if h1 else ''
    out[label] = info

with open('_race_debug.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('done')
