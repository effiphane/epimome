# -*- coding: utf-8 -*-
"""给现有 data.js 补上状态 + 修正毛色（一次性脚本）"""
import re, json, time
from collections import Counter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import scrape_and_build as sb

WORKERS = 5
DELAY = 0.15


def get_status_color(hid):
    r = sb.fetch(f'https://db.netkeiba.com/horse/{hid}/')
    if not r:
        return None, None
    soup = BeautifulSoup(r.text, 'html.parser')
    return sb.detect_status(soup), sb.extract_color(soup)


def main():
    content = open('data.js', encoding='utf-8').read()
    m = re.search(r'=\s*(\[.*\])\s*;', content, re.S)
    data = json.loads(m.group(1))

    ids = [h['id'] for h in data if h.get('id')]
    results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(get_status_color, hid): hid for hid in ids}
        for fut in as_completed(futs):
            hid = futs[fut]
            try:
                results[hid] = fut.result()
            except Exception:
                results[hid] = (None, None)
            done += 1
            if done % 200 == 0:
                print(f'{done}/{len(ids)}', flush=True)
            time.sleep(DELAY / WORKERS)

    for h in data:
        status, color = results.get(h['id'], (None, None))
        h['status'] = status
        if color:
            h['color'] = color

    js = '// 本文件由 scrape_and_build.py 自动生成\nconst 产驹数据 = ' + \
        json.dumps(data, ensure_ascii=False) + ';\n'
    with open('data.js', 'w', encoding='utf-8') as f:
        f.write(js)
    print('状态分布:', dict(Counter(h.get('status') for h in data)), flush=True)
    print('毛色分布:', dict(Counter(h.get('color') for h in data)), flush=True)


if __name__ == '__main__':
    main()
