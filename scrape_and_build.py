# -*- coding: utf-8 -*-
"""
netkeiba 产驹数据抓取 → 直接生成 data.js
用于 GitHub Actions 定时自动更新；也可本地运行：python scrape_and_build.py
"""
import requests, re, time, json, sys
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
SIRES = {
    'エピファネイア': '2010104155',
    'エフフォーリア': '2018105027',
}
SIRES_EN = {'エピファネイア': 'Epiphaneia', 'エフフォーリア': 'Efforia'}
WORKERS = 3
DELAY = 0.4
MIN_RECORDS = 1000  # 数据量异常时拒绝覆盖，防止把网站数据清空


def fetch(url):
    for _ in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.encoding = 'euc-jp'
            if r.status_code == 200:
                return r
        except Exception:
            time.sleep(2)
    return None


def scrape_list(sire_id):
    """列表页：拿到 马名/id/性别/生年/调教师/母名/母父/马主/牧场"""
    horses = {}
    page = 1
    while True:
        url = f'https://db.netkeiba.com/horse/list.html?sire_id={sire_id}&range=all&page={page}'
        r = fetch(url)
        if not r:
            break
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='horse_list_table')
        if not table:
            break

        for tr in table.find_all('tr')[1:]:
            cells = tr.find_all('td')
            if len(cells) < 10:
                continue
            a = cells[1].find('a')
            if not a:
                continue
            name = a.get_text(strip=True)
            m = re.search(r'/horse/(\d+)/', a['href'])
            if not m or name in horses:
                continue

            def cell_text(i):
                return cells[i].get_text(strip=True) if i < len(cells) else ''

            def link_text(i):
                la = cells[i].find('a')
                return la.get_text(strip=True) if la else cell_text(i)

            horses[name] = {
                'horse_id': m.group(1),
                'sex': cell_text(2),
                'birth_year': cell_text(3),
                'trainer': cell_text(5).replace('[西]', '栗').replace('[東]', '美'),
                'dam': re.sub(r'\[\]$', '', link_text(7)).strip(),
                'bms': re.sub(r'\[\]$', '', link_text(8)).strip(),
                'owner': cell_text(9),
                'breeder': cell_text(10),
            }

        max_pg = page
        for a in soup.find_all('a', href=True):
            m = re.search(r'page=(\d+)', a['href'])
            if m:
                max_pg = max(max_pg, int(m.group(1)))
        if page >= max_pg:
            break
        page += 1
        time.sleep(0.4)

    print(f'  列表页完成: {len(horses)} 匹', flush=True)
    return horses


def scrape_detail(hid):
    """详情页：拿到 英字名/生日(M.D)/毛色/拍卖价/募集价/成绩"""
    r = fetch(f'https://db.netkeiba.com/horse/{hid}/')
    if not r:
        return {}
    soup = BeautifulSoup(r.text, 'html.parser')
    d = {}

    title = soup.find('title')
    if title:
        m = re.search(r'\(([^)]+)\)', title.text.strip())
        if m:
            d['en'] = m.group(1).strip()

    h1 = soup.find('h1')
    if h1:
        txt = h1.get_text(strip=True)
        for c in ['黒鹿毛', '青鹿毛', '青毛', '鹿毛', '栗毛', '芦毛', '白毛', '栃栗毛']:
            if c in txt:
                d['color'] = c
                break

    for table in soup.find_all('table'):
        for tr in table.find_all('tr'):
            th = tr.find('th')
            td = tr.find('td')
            if not th or not td:
                continue
            k = th.get_text(strip=True)
            v = td.get_text(strip=True)
            if k == '生年月日':
                m = re.search(r'(\d+)年(\d+)月(\d+)日', v)
                if m:
                    d['bd'] = f'{m.group(2)}.{m.group(3)}'
            elif k == 'セリ取引価格':
                if v and v != '-':
                    d['auction'] = v
            elif k == '募集情報':
                d['raise'] = v
            elif k == '通算成績':
                rec = re.sub(r'\s*\[.*\]', '', v)
                rec = rec.replace('戦', '战').replace('勝', '胜')
                d['rec'] = rec
    return d


def main():
    t0 = time.time()
    all_records = []
    for sire, sire_id in SIRES.items():
        print(f'== {sire} ({SIRES_EN[sire]}) ==', flush=True)
        horses = scrape_list(sire_id)
        print(f'  抓取详情页 {len(horses)} 匹...', flush=True)

        items = list(horses.items())
        detail_map = {}
        done = 0
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(scrape_detail, h['horse_id']): name for name, h in items}
            for fut in as_completed(futs):
                name = futs[fut]
                try:
                    detail_map[name] = fut.result()
                except Exception:
                    detail_map[name] = {}
                done += 1
                if done % 100 == 0:
                    print(f'    {done}/{len(items)}', flush=True)
                time.sleep(DELAY / WORKERS)

        for name, h in items:
            det = detail_map.get(name, {})
            all_records.append({
                'name': name,
                'en': det.get('en'),
                'dam': h['dam'] or None,
                'bd': det.get('bd') or h['birth_year'] or None,
                'sex': h['sex'] or None,
                'color': det.get('color'),
                'bms': h['bms'] or None,
                'farm': h['breeder'] or None,
                'owner': h['owner'] or None,
                'trainer': h['trainer'] or None,
                'raise': det.get('raise'),
                'auction': det.get('auction'),
                'rec': det.get('rec'),
                'sire': sire,
                'sireEn': SIRES_EN[sire],
            })

    print(f'总计 {len(all_records)} 匹, 用时 {time.time() - t0:.0f}s', flush=True)
    if len(all_records) < MIN_RECORDS:
        sys.exit(f'数据量异常({len(all_records)} < {MIN_RECORDS})，放弃更新 data.js')

    js = '// 本文件由 scrape_and_build.py 自动生成\nconst 产驹数据 = ' + \
        json.dumps(all_records, ensure_ascii=False) + ';\n'
    with open('data.js', 'w', encoding='utf-8') as f:
        f.write(js)
    print('已写入 data.js', flush=True)


if __name__ == '__main__':
    main()
