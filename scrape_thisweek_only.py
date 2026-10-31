# -*- coding: utf-8 -*-
"""只抓取本周出马数据（含赛事级别/开赛时间），供每日定时任务用"""
import sys
import scrape_and_build as sb

sb.check_cookie_status()
runners = sb.scrape_thisweek()
if len(runners) < sb.MIN_THISWEEK:
    # 比赛空档期属于正常情况：保留旧数据，但不算失败
    print(f'本周出赛抓取异常（{len(runners)} 条 < {sb.MIN_THISWEEK}），保留旧数据', flush=True)
    sys.exit(0)
runners = sb.merge_thisweek(runners, sb.load_thisweek())
runners = sb.fill_results(runners)
runners = sb.dedupe_thisweek(runners)
sb.write_thisweek(runners)
try:
    sb.make_week_image(runners)
except Exception as e:
    print(f'出赛表图片生成失败（不影响数据）：{e}')
# 只统计本周的条目：文件里还会保留上一周的数据用于兜底，不能按总条数报
sb.add_update_entry(f'更新本周出赛（{sb.thisweek_count(runners)}匹）')
