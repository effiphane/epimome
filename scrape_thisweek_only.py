# -*- coding: utf-8 -*-
"""只抓取本周出马数据（含赛事级别），供每日定时任务用"""
import scrape_and_build as sb

runners = sb.scrape_thisweek()
sb.write_thisweek(runners)
