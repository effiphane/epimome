# -*- coding: utf-8 -*-
"""
把 种马数据.xlsx 里「次走/近况」列的内容，生成网站用的 moves.js

用法：双击「发布动向.bat」即可，一般不用直接运行这个文件。
想改 Excel 的位置，改下面的 XLSX 变量。
"""
import io
import json
import os
import re
import sys
import datetime

XLSX = r'C:\Users\Forls\Desktop\First\种马数据.xlsx'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'moves.js')


def clean(v):
    """单元格 → 干净字符串（保留换行，压缩多余空格）"""
    if v is None:
        return ''
    s = str(v).replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()


def load_log():
    """读现有的改动日志（越新越靠前）"""
    if not os.path.exists(OUT):
        return []
    try:
        txt = io.open(OUT, encoding='utf-8').read()
        m = re.search(r'const\s*动向日志\s*=\s*(\[.*?\])\s*;', txt, re.S)
        return json.loads(m.group(1)) if m else []
    except Exception:
        return []


def load_prev():
    """读现有的 moves.js，用来判断哪些动向是新改的（保留原来的更新日期）"""
    if not os.path.exists(OUT):
        return {}
    try:
        txt = io.open(OUT, encoding='utf-8').read()
        m = re.search(r'const\s*最新动向\s*=\s*(\{.*\})\s*;', txt, re.S)
        return json.loads(m.group(1)) if m else {}
    except Exception:
        return {}


def main():
    if not os.path.exists(XLSX):
        print('找不到 Excel：%s' % XLSX)
        print('请确认文件还在那里，或者修改 sync_moves.py 里的 XLSX 路径。')
        return 1

    try:
        import openpyxl
    except ImportError:
        print('缺少 openpyxl，请先运行：py -m pip install openpyxl')
        return 1

    try:
        wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    except Exception as e:
        print('Excel 打不开（可能正在被 Excel 占用，先关掉 Excel 再试）：%s' % e)
        return 1

    today = datetime.date.today().isoformat()
    prev = load_prev()
    result = {}
    changed = []

    for ws in wb.worksheets:
        rows = ws.iter_rows(min_row=1, values_only=True)
        header = next(rows, None)
        if not header:
            continue
        header = [clean(h) for h in header]

        # 按表头名字找列，不写死位置
        name_col = next((i for i, h in enumerate(header) if h == '马名'), None)
        if name_col is None:
            name_col = next((i for i, h in enumerate(header) if '马名' in h), None)
        move_col = next((i for i, h in enumerate(header)
                         if '次走' in h or '近况' in h), None)
        if name_col is None or move_col is None:
            print('工作表「%s」找不到「马名」或「次走/近况」列，跳过' % ws.title)
            continue

        for row in rows:
            if not row or len(row) <= max(name_col, move_col):
                continue
            name = clean(row[name_col])
            text = clean(row[move_col])
            if not name or not text:
                continue
            old = prev.get(name)
            # 内容没变就沿用上次的日期，变了就记今天
            stamp = old.get('updated') if (old and old.get('text') == text) else today
            if not old or old.get('text') != text:
                changed.append(name)
            result[name] = {'text': text, 'updated': stamp}

    body = json.dumps(result, ensure_ascii=False, indent=2) if result else '{}'

    # 内容有变化时，同步改掉 index.html 里的版本号，
    # 否则浏览器会继续用缓存里的旧 moves.js（Cloudflare 默认缓存 4 小时）
    old = ''
    if os.path.exists(OUT):
        old = io.open(OUT, encoding='utf-8').read()
    new_version = None
    if prev != result:
        new_version = datetime.datetime.now().strftime('%Y%m%d%H%M')
        html_path = os.path.join(HERE, 'index.html')
        if os.path.exists(html_path):
            html = io.open(html_path, encoding='utf-8', newline='').read()
            html2 = re.sub(r'moves\.js\?v=\d+', 'moves.js?v=' + new_version, html)
            if html2 != html:
                io.open(html_path, 'w', encoding='utf-8', newline='').write(html2)

    # 改动日志：每匹马的动向一旦和上次不同，就追加一条（保留历史，不覆盖）
    log = load_log()

    def last_for(nm):
        for e in log:
            if e.get('name') == nm:
                return e
        return None

    added = []
    for nm, rec in result.items():
        last = last_for(nm)
        if not last or last.get('text') != rec['text']:
            added.append({'date': rec.get('updated') or today, 'name': nm, 'text': rec['text']})
    if added:
        log = added + log
    log = log[:300]   # 只保留最近 300 条

    out = (
        '// 本文件由「发布动向」自动生成，内容来自 种马数据.xlsx 的「次走/近况」列\n'
        '// 不要手动改这个文件 —— 改 Excel 的那一栏，然后双击「发布动向.bat」\n'
        'const 最新动向 = %s;\n\n'
        'const 动向日志 = %s;\n' % (body, json.dumps(log, ensure_ascii=False, indent=2))
    )
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(out)

    print('读取完成：%d 匹马写了次走/近况' % len(result))
    if new_version:
        print('已更新资源版本号 → %s（让浏览器重新加载）' % new_version)
    if changed:
        print('本次更新了 %d 匹：%s' % (len(changed), '、'.join(changed[:8]) +
                                       ('…' if len(changed) > 8 else '')))
    else:
        print('内容没有变化')
    return 0


if __name__ == '__main__':
    sys.exit(main())
