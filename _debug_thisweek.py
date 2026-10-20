# -*- coding: utf-8 -*-
"""调试2：dump netkeiba 本周出马页面完整文本和结构"""
import requests, json
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

r = requests.get('https://db.netkeiba.com/sire/thisweek/2010104155/', headers=HEADERS, timeout=30)
r.encoding = 'euc-jp'
soup = BeautifulSoup(r.text, 'html.parser')

txt = soup.get_text(' ', strip=True)
out = {
    '全文长度': len(txt),
    '全文前3000字': txt[:3000],
    'HTML长度': len(r.text),
    # 找所有含 horse 的 href
    'horse链接': [a['href'][:60] for a in soup.find_all('a', href=True) if '/horse/' in a['href']][:20],
    # 找 script 标签里的数据线索
    'script数量': len(soup.find_all('script')),
}

with open('_thisweek_debug.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('done')
