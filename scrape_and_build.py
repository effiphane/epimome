# -*- coding: utf-8 -*-
"""
netkeiba 产驹数据抓取 → 生成 data.js + 下载照片到 photos/
抓取内容：基本信息 + 马匹ID + 照片 + 5代血统
用于 GitHub Actions 定时自动更新；也可本地运行：python scrape_and_build.py
"""
import requests, re, time, json, sys, os, glob
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
PHOTO_DIR = 'photos'
NETKEIBA_COOKIE = (os.environ.get('NETKEIBA_COOKIE', '')
                   .replace('；', ';')      # 兼容中文输入法的全角分号「；」
                   .replace('　', ' ')      # 兼容全角空格
                   .strip())  # 登录cookie（本周出马完整列表需要会员）


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


def fetch_thisweek(url):
    """带登录 cookie 抓取（本周出马完整列表需要会员）"""
    headers = dict(HEADERS)
    if NETKEIBA_COOKIE:
        headers['Cookie'] = NETKEIBA_COOKIE
    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=30)
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
                'trainer': cell_text(5).replace('[西]', '栗').replace('[東]', '美').replace('[地]', '地'),
                'dam': re.sub(r'\[\]$', '', link_text(7)).strip(),
                'bms': re.sub(r'\[\]$', '', link_text(8)).strip(),
                'owner': cell_text(9),
                'breeder': cell_text(10),
                'prize': cell_text(11),
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


def clean_ped_name(text):
    text = text.strip()
    text = re.sub(r'\[.*?\]', '', text)
    m = re.search(r'\d{4}|\d{1,2}-[a-z]|鹿毛|黒鹿毛|青鹿毛|青毛|栗毛|芦毛|白毛|栃栗毛', text)
    if m:
        text = text[:m.start()]
    text = re.sub(r'\s*\([米英仏愛加豪独伊露葡新]+\)\s*$', '', text)
    return text.strip()


def parse_pedigree(table):
    """把 netkeiba 血统表解析成嵌套树 {n:名字, i:id, s:父, d:母}"""
    cells = []
    for tr in table.find_all('tr'):
        for td in tr.find_all('td'):
            a = td.find('a')
            if not a:
                continue
            text = td.get_text(strip=True)
            m = re.search(r'/horse/([^/]+)/', a.get('href', ''))
            hid = m.group(1) if m else ''
            rs = td.get('rowspan', '') or '1'
            cells.append({'n': clean_ped_name(text), 'i': hid, 'rs': int(rs)})

    idx = [0]

    def build():
        node = cells[idx[0]]
        idx[0] += 1
        r = {'n': node['n'], 'i': node['i']}
        if node['rs'] > 1:
            r['s'] = build()
            r['d'] = build()
        return r

    if not cells:
        return None
    sire = build()
    dam = build() if idx[0] < len(cells) else None
    return {'s': sire, 'd': dam}


def parse_year(v):
    if not v:
        return None
    m = re.search(r'\d{4}', str(v))
    return int(m.group(0)) if m else None


def parse_prize(v):
    if not v:
        return None
    try:
        return float(str(v).replace(',', '').strip())
    except ValueError:
        return None


def scrape_results(hid):
    """战绩页：抓取全部比赛履历（含人气，按表头定位列，避免索引错位）"""
    r = fetch(f'https://db.netkeiba.com/horse/result/{hid}/')
    if not r:
        return []
    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find('table', class_='db_h_race_results')
    if not table:
        return []
    headers = []
    thead = table.find('thead') or table.find('tr')
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all(['th', 'td'])]

    def col(*names):
        for i, h in enumerate(headers):
            if any(n in h for n in names):
                return i
        return None

    i_date = col('日付')
    i_venue = col('開催')
    i_race = col('レース名')
    i_pos = col('着順')
    i_jockey = col('騎手')
    i_dist = col('距離')
    i_pop = col('人気')

    races = []
    for tr in table.find_all('tr')[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all('td')]
        if not cells:
            continue

        def get(i):
            return cells[i] if i is not None and i < len(cells) else ''

        races.append({
            'date': get(i_date), 'venue': get(i_venue), 'race': get(i_race),
            'pos': get(i_pos), 'jockey': get(i_jockey), 'dist': get(i_dist),
            'pop': get(i_pop),
        })
    return races


def extract_color(soup):
    """从 horse_title 提取毛色"""
    colors = ['黒鹿毛', '青鹿毛', '青毛', '鹿毛', '栗毛', '芦毛', '白毛', '栃栗毛']
    title_div = soup.find('div', class_='horse_title')
    if title_div:
        txt01 = title_div.find('p', class_='txt_01')
        if txt01:
            txt = txt01.get_text(strip=True)
            for c in colors:
                if c in txt:
                    return c
    for table in soup.find_all('table'):
        for tr in table.find_all('tr'):
            th = tr.find('th')
            td = tr.find('td')
            if th and td and th.get_text(strip=True) == '毛色':
                txt = td.get_text(strip=True)
                for c in colors:
                    if c in txt:
                        return c
    return None


def detect_status(soup):
    """判断马匹状态：現役 / 退役・繁殖 / 退役"""
    txt = soup.get_text()
    if '現役' in txt:
        return '現役'
    for a in soup.find_all('a', href=True):
        if a.get_text(strip=True) in ('種牡馬', '繁殖牝馬'):
            return '退役・繁殖'
    if '抹消' in txt or '引退' in txt:
        return '退役'
    return None


def check_jbis_breeding(name, sex):
    """查 JBIS 确认马匹是否已入繁殖（種牡馬/繁殖牝馬），是返回 '退役・繁殖'，否则 None。

    netkeiba 对「退役但产驹还没出生」的繁殖马会误标为退役（页面没有種牡馬/繁殖牝馬标签），
    用 JBIS 交叉核对纠正。失败（超时/403/解析异常/找不到）一律返回 None，不影响原状态。
    """
    if sex not in ('牡', '牝'):
        return None
    try:
        # 1) 用马名搜索 JBIS，取第一个结果（同名马按年份区分的情况很少，先取第一个）
        r = requests.get('https://www.jbis.or.jp/horse/result/',
                         params={'keyword': name}, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        jbis_id = None
        for a in soup.find_all('a', href=True):
            m = re.search(r'/horse/(\d+)/', a['href'])
            if m:
                jbis_id = m.group(1)
                break
        if not jbis_id:
            return None
        # 2) 访问详情页，判断繁殖标识
        r2 = requests.get(f'https://www.jbis.or.jp/horse/{jbis_id}/', headers=HEADERS, timeout=15)
        if r2.status_code != 200:
            return None
        r2.encoding = 'utf-8'
        txt = r2.text
        if sex == '牝' and ('繁殖牝馬情報' in txt or '繁殖牝馬' in txt):
            return '退役・繁殖'
        if sex == '牡' and ('種牡馬情報' in txt or '種牡馬' in txt):
            return '退役・繁殖'
    except Exception:
        pass
    return None


def scrape_detail(session, hid):
    """详情页：拿到 英字名/生日/毛色/拍卖价/募集价/成绩/照片URL"""
    r = session.get(f'https://db.netkeiba.com/horse/{hid}/', timeout=30)
    if r.status_code != 200:
        return {}
    r.encoding = 'euc-jp'
    soup = BeautifulSoup(r.text, 'html.parser')
    d = {}

    title = soup.find('title')
    if title:
        m = re.search(r'\(([^)]+)\)', title.text.strip())
        if m:
            d['en'] = m.group(1).strip()

    d['color'] = extract_color(soup)

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

    for img in soup.find_all('img'):
        src = img.get('src', '')
        if 'show_photo.php' in src:
            d['photo_url'] = src
            break

    d['status'] = detect_status(soup)
    return d


def download_photo(session, hid, url):
    """下载照片到 photos/，已存在则跳过"""
    existing = glob.glob(os.path.join(PHOTO_DIR, f'{hid}.*'))
    if existing:
        return os.path.relpath(existing[0], '.').replace('\\', '/')
    try:
        r = session.get(url, timeout=30)
        ct = r.headers.get('content-type', '')
        if r.status_code == 200 and 'image' in ct:
            ext = '.png' if 'png' in ct else ('.gif' if 'gif' in ct else '.jpg')
            path = os.path.join(PHOTO_DIR, f'{hid}{ext}')
            with open(path, 'wb') as f:
                f.write(r.content)
            return f'{PHOTO_DIR}/{hid}{ext}'
    except Exception:
        pass
    return None


def scrape_ped(hid):
    """血统页：解析 5 代血统树"""
    r = fetch(f'https://db.netkeiba.com/horse/ped/{hid}/')
    if not r:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    tables = soup.find_all('table')
    if not tables:
        return None
    return parse_pedigree(tables[0])


def load_old_ped():
    """从旧 data.js 读取血统映射（血统不变，可复用省请求）"""
    ped_map = {}
    try:
        if not os.path.exists('data.js'):
            return ped_map
        with open('data.js', encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'=\s*(\[.*\])\s*;', content, re.S)
        if m:
            old = json.loads(m.group(1))
            for h in old:
                if h.get('id') and h.get('ped'):
                    ped_map[str(h['id'])] = h['ped']
    except Exception:
        pass
    return ped_map


def scrape_horse(hid, ped_map, name=None, sex=None):
    """一匹马：详情 + 照片下载 + 血统（可复用）+ 战绩 + 繁殖状态 JBIS 核对"""
    session = requests.Session()
    session.headers.update(HEADERS)
    detail = scrape_detail(session, hid)
    url = detail.pop('photo_url', None)
    detail['photo'] = download_photo(session, hid, url) if url else None
    detail['ped'] = ped_map.get(str(hid)) or scrape_ped(hid)
    detail['races'] = scrape_results(hid)
    # 退役马交叉核对 JBIS，纠正「退役但实际已入繁殖」的误标
    if detail.get('status') == '退役' and name and sex in ('牡', '牝'):
        breed = check_jbis_breeding(name, sex)
        if breed:
            detail['status'] = breed
    return detail


def add_update_entry(text):
    """往 updates.js 的「数据更新」列表加一条记录（同一天可多条，同类不重复）"""
    import datetime
    today = datetime.date.today().isoformat()
    entry = {'date': today, 'text': text}
    func = []
    data = []
    if os.path.exists('updates.js'):
        with open('updates.js', encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'const 功能更新 = (\[.*?\]);', content, re.S)
        if m:
            try:
                func = json.loads(m.group(1))
            except Exception:
                func = []
        m2 = re.search(r'const 数据更新 = (\[.*?\]);', content, re.S)
        if m2:
            try:
                data = json.loads(m2.group(1))
            except Exception:
                data = []
    if not any(x.get('date') == today and x.get('text') == text for x in data):
        data = [entry] + data
    js = '// 数据更新由脚本自动维护；功能更新请手动编辑\n'
    js += 'const 功能更新 = ' + json.dumps(func, ensure_ascii=False) + ';\n'
    js += 'const 数据更新 = ' + json.dumps(data, ensure_ascii=False) + ';\n'
    with open('updates.js', 'w', encoding='utf-8') as f:
        f.write(js)


def update_changelog(count):
    """更新产驹数据时记录一条（兼容旧调用）"""
    add_update_entry(f'更新产驹数据（{count}匹）')


def classify_race(name):
    """根据赛事名判断赛事级别"""
    if not name:
        return ''
    if re.search(r'\(G[I123]\)', name):
        return '分级赛'
    if 'リステッド' in name or re.search(r'\(L\)', name):
        return '表列赛'
    if 'オープン' in name or '(OP)' in name:
        return '公开赛'
    if '新馬' in name:
        return '新马'
    if '未勝利' in name:
        return '未胜利'
    if '1勝' in name:
        return '一胜级'
    if '2勝' in name:
        return '二胜级'
    if '3勝' in name:
        return '三胜级'
    return ''  # 无法判断则留空


def classify_race_from_title(title):
    """从赛事页标题判断准确级别"""
    if not title:
        return ''
    if re.search(r'\(G', title):
        return '分级赛'
    if 'リステッド' in title or re.search(r'\(L\)', title):
        return '表列赛'
    if 'オープン' in title:
        return '公开赛'
    if '新馬' in title:
        return '新马'
    if '未勝利' in title:
        return '未胜利'
    if re.search(r'[1１]勝', title):
        return '一胜级'
    if re.search(r'[2２]勝', title):
        return '二胜级'
    if re.search(r'[3３]勝', title):
        return '三胜级'
    return ''


_race_cls_cache = {}


def get_race_class(race_id):
    """从赛事详情页获取准确级别（带缓存）"""
    if not race_id:
        return ''
    if race_id in _race_cls_cache:
        return _race_cls_cache[race_id]
    cls = ''
    try:
        r = requests.get(f'https://race.netkeiba.com/race/result.html?race_id={race_id}',
                         headers=HEADERS, timeout=30)
        r.encoding = 'utf-8'
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            title = soup.title.get_text(strip=True) if soup.title else ''
            cls = classify_race_from_title(title)
    except Exception:
        pass
    _race_cls_cache[race_id] = cls
    return cls


def date_from_race_id(race_id):
    """从地方赛事(nar)race_id 提取真实日期，失败返回 None。

    nar 的 race_id 是 12 位：YYYY(4) + 赛场代码(2) + 月(2) + 日(2) + 场次(2)
    例如 202635102011 → 2026 35(盛冈) 10月 20日 11R → 10月20日。
    netkeiba 的「本周出马」页面有时会把相邻几天的比赛归到同一个日期标题下
    导致错位，用 race_id 里的月日兜底更可靠。
    """
    if not race_id or len(race_id) < 10:
        return None
    try:
        mo, d = int(race_id[6:8]), int(race_id[8:10])
    except ValueError:
        return None
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f'{mo}月{d}日'


def _month_day(s):
    """把 '10月18日' 或 '2026/10/18' 转成 '1018'，用于比较日期"""
    s = s or ''
    m = re.search(r'(\d{1,2})月(\d{1,2})日', s)
    if m:
        return f'{int(m.group(1)):02d}{int(m.group(2)):02d}'
    m = re.search(r'/(\d{1,2})/(\d{1,2})', s)
    if m:
        return f'{int(m.group(1)):02d}{int(m.group(2)):02d}'
    return None


def filter_false_runners(runners):
    """过滤掉 netkeiba 页面误标的「报了名但没出赛」的记录。

    对每条中央・結果確定的记录，查该马真实战绩，若战绩里没有同月同日的比赛，
    说明这匹马当天其实没出赛（页面残留的出马表），丢弃该记录。
    """
    cache = {}
    out = []
    for r in runners:
        keep = True
        if r.get('region') == '中央' and r.get('status') == '結果確定' and r.get('id'):
            hid = r['id']
            if hid not in cache:
                try:
                    cache[hid] = [race.get('date') or '' for race in scrape_results(hid)]
                except Exception:
                    cache[hid] = None
            dates = cache[hid]
            if dates is not None:
                target = _month_day(r.get('date'))
                if target and not any(_month_day(d) == target for d in dates):
                    keep = False
        if keep:
            out.append(r)
    return out


def scrape_thisweek():
    """抓取本周出马（两个种马 × 中央/地方）"""
    runners = []
    for sire, sire_id in SIRES.items():
        for rtype, region in (('1', '中央'), ('2', '地方')):
            url = f'https://db.netkeiba.com/sire/thisweek/{sire_id}/?type={rtype}'
            r = fetch_thisweek(url)
            if not r:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for block in soup.find_all('section', class_='EntryHorseList_Block'):
                day_el = block.find('h3', class_='EntryHorseList_Day')
                day = day_el.get_text(strip=True) if day_el else ''
                for race_block in block.find_all('section', class_='EntryHorseList_RaceBlock'):
                    info = race_block.find('div', class_='EntryHorseList_RaceInfo')
                    race_num = race_name = race_status = ''
                    race_id = ''
                    if info:
                        rn = info.find('span', class_='EntryHorseList_RaceNum')
                        race_num = rn.get_text(strip=True) if rn else ''
                        rnm = info.find('span', class_='EntryHorseList_RaceName')
                        race_name = rnm.get_text(strip=True) if rnm else ''
                        rs = info.find('span', class_='EntryHorseList_RaceStatus')
                        race_status = rs.get_text(strip=True) if rs else ''
                        rlink = info.find('a', class_='EntryHorseList_RaceLink')
                        if rlink:
                            m = re.search(r'race_id=(\d+)', rlink.get('href', ''))
                            race_id = m.group(1) if m else ''
                    cls = get_race_class(race_id) if race_id else classify_race(race_name)
                    for li in race_block.find_all('li'):
                        na = li.find('a', class_='EntryHorseList_HorseName')
                        if not na:
                            continue
                        name = na.get_text(strip=True)
                        m = re.search(r'/horse/(\d+)/', na.get('href', ''))
                        hid = m.group(1) if m else ''
                        j_el = li.find('span', class_='EntryHorseList_Jockey')
                        jockey = j_el.get_text(strip=True) if j_el else ''
                        f_el = li.find('span', class_='EntryHorseList_Favorite')
                        fav = f_el.get_text(strip=True) if f_el else ''
                        o_el = li.find('span', class_='EntryHorseList_Order')
                        order = o_el.get_text(strip=True) if o_el else ''
                        n_el = li.find('div', class_='PcHorseNo')
                        num = n_el.get_text(strip=True) if n_el else ''
                        date = (date_from_race_id(race_id) if region == '地方' else None) or day
                        runners.append({
                            'date': date, 'race': f'{race_num} {race_name}'.strip(),
                            'cls': cls,
                            'status': race_status, 'name': name, 'id': hid,
                            'jockey': jockey, 'fav': fav, 'order': order, 'num': num,
                            'sire': sire, 'region': region,
                        })
    return filter_false_runners(runners)


def write_thisweek(runners):
    js = '// 本文件由 scrape_and_build.py 自动生成\nconst 本周出马 = ' + \
        json.dumps(runners, ensure_ascii=False) + ';\n'
    with open('thisweek.js', 'w', encoding='utf-8') as f:
        f.write(js)
    print(f'已写入 thisweek.js（{len(runners)} 匹出赛）', flush=True)


def main():
    t0 = time.time()
    os.makedirs(PHOTO_DIR, exist_ok=True)
    ped_map = load_old_ped()
    all_records = []
    for sire, sire_id in SIRES.items():
        print(f'== {sire} ({SIRES_EN[sire]}) ==', flush=True)
        horses = scrape_list(sire_id)
        print(f'  抓取详情+血统+照片 {len(horses)} 匹...', flush=True)

        items = list(horses.items())
        detail_map = {}
        done = 0
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(scrape_horse, h['horse_id'], ped_map, name, h['sex']): name for name, h in items}
            for fut in as_completed(futs):
                name = futs[fut]
                try:
                    detail_map[name] = fut.result()
                except Exception:
                    detail_map[name] = {}
                done += 1
                if done % 50 == 0:
                    print(f'    {done}/{len(items)}', flush=True)
                time.sleep(DELAY / WORKERS)

        for name, h in items:
            det = detail_map.get(name, {})
            all_records.append({
                'name': name,
                'id': h['horse_id'],
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
                'status': det.get('status'),
                'photo': det.get('photo'),
                'ped': det.get('ped'),
                'year': parse_year(h['birth_year']),
                'prize': parse_prize(h['prize']),
                'races': det.get('races', []),
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
    update_changelog(len(all_records))
    write_thisweek(scrape_thisweek())


if __name__ == '__main__':
    main()
