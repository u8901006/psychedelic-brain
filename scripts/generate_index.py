#!/usr/bin/env python3
"""Generate index.html listing all psychedelic daily reports."""

import glob
import os
from datetime import datetime

html_files = sorted(glob.glob("docs/psychedelic-*.html"), reverse=True)
links = ""
for f in html_files[:60]:
    name = os.path.basename(f)
    date = name.replace("psychedelic-", "").replace(".html", "")
    try:
        d = datetime.strptime(date, "%Y-%m-%d")
        date_display = f"{d.year}年{d.month}月{d.day}日"
    except Exception:
        date_display = date
    weekday = (
        ["一", "二", "三", "四", "五", "六", "日"][
            datetime.strptime(date, "%Y-%m-%d").weekday()
        ]
        if len(date) == 10
        else ""
    )
    links += f'<li><a href="{name}">🍄 {date_display}（週{weekday}）</a></li>\n'

total = len(html_files)

index = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Psychedelic Brain · 迷幻研究文獻日報</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🍄</text></svg>"/>
<style>
  :root {{ --bg: #0a0a12; --surface: rgba(255,255,255,0.03); --line: rgba(255,255,255,0.07); --text: #E8E0F0; --muted: #78909C; --accent: #A78BFA; --accent-soft: rgba(139,92,246,0.10); }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0a0a12; color: var(--text); font-family: -apple-system, "PingFang TC", "Helvetica Neue", Arial, sans-serif; min-height: 100vh; }}
  body::before {{ content: ''; position: fixed; bottom: -200px; right: -200px; width: 900px; height: 900px; border-radius: 50%; background: radial-gradient(circle, rgba(139,92,246,0.10) 0%, transparent 70%); pointer-events: none; z-index: 0; }}
  body::after {{ content: ''; position: fixed; top: -250px; left: -250px; width: 700px; height: 700px; border-radius: 50%; background: radial-gradient(circle, rgba(6,182,212,0.08) 0%, transparent 70%); pointer-events: none; z-index: 0; }}
  .container {{ position: relative; z-index: 1; max-width: 640px; margin: 0 auto; padding: 80px 24px; }}
  .logo {{ font-size: 48px; text-align: center; margin-bottom: 16px; }}
  h1 {{ text-align: center; font-size: 24px; color: #fff; margin-bottom: 8px; }}
  .subtitle {{ text-align: center; color: var(--accent); font-size: 14px; margin-bottom: 48px; }}
  .count {{ text-align: center; color: var(--muted); font-size: 13px; margin-bottom: 32px; }}
  ul {{ list-style: none; }}
  li {{ margin-bottom: 8px; }}
  a {{ color: var(--text); text-decoration: none; display: block; padding: 14px 20px; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; transition: all 0.2s; font-size: 15px; }}
  a:hover {{ background: var(--accent-soft); border-color: var(--accent); transform: translateX(4px); }}
  .clinic-banner {{ margin: 40px 0 20px; padding: 16px 20px; background: linear-gradient(135deg, rgba(139,92,246,0.08) 0%, rgba(6,182,212,0.08) 100%); border: 1px solid rgba(139,92,246,0.15); border-radius: 12px; text-align: center; }}
  .clinic-banner a {{ background: none; border: none; padding: 0; color: #22D3EE; font-weight: 600; }}
  .clinic-banner a:hover {{ color: #A78BFA; transform: none; }}
  footer {{ margin-top: 56px; text-align: center; font-size: 12px; color: #546E7A; }}
  footer a {{ display: inline; padding: 0; background: none; border: none; color: #546E7A; }}
  footer a:hover {{ color: var(--accent); }}
</style>
</head>
<body>
<div class="container">
  <div class="logo">🍄</div>
  <h1>Psychedelic Brain</h1>
  <p class="subtitle">迷幻研究文獻日報 · 每日自動更新</p>
  <p class="count">共 {total} 期日報</p>
  <ul>{links}</ul>
  <div class="clinic-banner">
    <a href="https://www.leepsyclinic.com/" target="_blank">🧠 李政洋身心診所</a>
  </div>
  <footer>
    <p>Powered by PubMed + Zhipu AI · <a href="https://github.com/u8901006/psychedelic-brain">GitHub</a></p>
  </footer>
</div>
</body>
</html>"""

with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(index)
print("Index page generated")
