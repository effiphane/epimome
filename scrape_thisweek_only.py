# -*- coding: utf-8 -*-
"""只抓取本周出马数据（含赛事级别/开赛时间），供每日定时任务用"""
import sys
import scrape_and_build as sb

runners = sb.scrape_thisweek()
if len(runners) < sb.MIN_THISWEEK:
    sys.exit(f'本周出赛抓取异常（{len(runners)} 条 < {sb.MIN_THISWEEK}），保留旧数据')
runners = sb.merge_thisweek(runners, sb.load_thisweek())
sb.write_thisweek(runners)
sb.bump_asset_version()
try:
    sb.make_week_image(runners)
except Exception as e:
    print(f'出赛表图片生成失败（不影响数据）：{e}')
sb.add_update_entry(f'更新本周出赛（{len(runners)}匹）')
