# -*- coding: utf-8 -*-
"""调试：检查 race_id 提取是否成功"""
import re, json
import scrape_and_build as sb
from bs4 import BeautifulSoup

r = sb.fetch('https://db.netkeiba.com/sire/thisweek/2010104155/')
soup = BeautifulSoup(r.text, 'html.parser')
out = []
for block in soup.find_all('section', class_='EntryHorseList_Block'):
    for rb in block.find_all('section', class_='EntryHorseList_RaceBlock'):
        info = rb.find('div', class_='EntryHorseList_RaceInfo')
        if not info:
            out.append({'race': '(无info)', 'href': '', 'race_id': ''})
            continue
        rnm = info.find('span', class_='EntryHorseList_RaceName')
        race_name = rnm.get_text(strip=True) if rnm else ''
        rlink = info.find('a', class_='EntryHorseList_RaceLink')
        href = rlink.get('href', '') if rlink else '(无链接)'
        m = re.search(r'race_id=(\d+)', href)
        race_id = m.group(1) if m else '(未匹配)'
        out.append({'race': race_name, 'href': href[:70], 'race_id': race_id})

with open('_race2_debug.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('done')
