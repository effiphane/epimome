# -*- coding: utf-8 -*-
"""调试3：dump 本周出马 runner 的 HTML 结构"""
import requests, re, json
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

r = requests.get('https://db.netkeiba.com/sire/thisweek/2010104155/', headers=HEADERS, timeout=30)
r.encoding = 'euc-jp'
soup = BeautifulSoup(r.text, 'html.parser')

out = {}
# 找马匹链接（/horse/{数字}/）
horse_links = [a for a in soup.find_all('a', href=True) if re.search(r'/horse/\d+/', a['href'])]
out['马匹链接数'] = len(horse_links)
if horse_links:
    a = horse_links[0]
    # 往上走到顶层 runner 容器（找含多个字段的祖先）
    p = a
    chain = []
    for _ in range(6):
        if p is None:
            break
        chain.append({'标签': p.name, 'class': str(p.get('class', '')), '文本': p.get_text(strip=True)[:60]})
        p = p.parent
    out['第一个马匹链接祖先链'] = chain
    # dump 倒数第2层（runner 行）的 HTML
    if len(chain) >= 2:
        # 找祖先链里文本长度合适的那个（runner 行）
        target = None
        pp = a
        for _ in range(6):
            if pp is None:
                break
            txt = pp.get_text(strip=True)
            if 30 < len(txt) < 200:
                target = pp
                break
            pp = pp.parent
        if target:
            out['runner行HTML'] = str(target)[:2000]

with open('_thisweek_debug.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('done')
