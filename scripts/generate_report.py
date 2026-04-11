#!/usr/bin/env python3
"""
Generate psychedelic daily report HTML using Zhipu AI.
Reads papers JSON, analyzes with AI, generates styled dark-themed HTML.
"""

import json
import sys
import os
import time
import argparse
from datetime import datetime, timezone, timedelta

import httpx

API_BASE = os.environ.get(
    "ZHIPU_API_BASE", "https://open.bigmodel.cn/api/coding/paas/v4"
)
MODEL_NAME = os.environ.get("ZHIPU_MODEL", "glm-4-plus")
CLINIC_URL = "https://www.leepsyclinic.com/"

SYSTEM_PROMPT = (
    "你是迷幻研究（psychedelic research）領域的資深研究員與科學傳播者。你的任務是：\n"
    "1. 從提供的醫學文獻中，篩選出最具臨床意義與研究價值的迷幻相關論文\n"
    "2. 對每篇論文進行繁體中文摘要、分類、PICO 分析\n"
    "3. 評估其臨床實用性（高/中/低）\n"
    "4. 生成適合醫療專業人員閱讀的日報\n\n"
    "輸出格式要求：\n"
    "- 語言：繁體中文（台灣用語）\n"
    "- 專業但易懂\n"
    "- 每篇論文需包含：中文標題、一句話總結、PICO分析、臨床實用性、分類標籤\n"
    "- 最後提供今日精選 TOP 3（最重要/最影響臨床實踐的論文）\n"
    "回傳格式必須是純 JSON，不要用 markdown code block 包裹。"
)


def load_papers(input_path: str) -> dict:
    if input_path == "-":
        data = json.load(sys.stdin)
    else:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    return data


def analyze_papers(api_key: str, papers_data: dict) -> dict:
    tz_taipei = timezone(timedelta(hours=8))
    date_str = papers_data.get("date", datetime.now(tz_taipei).strftime("%Y-%m-%d"))
    paper_count = papers_data.get("count", 0)
    papers_text = json.dumps(
        papers_data.get("papers", []), ensure_ascii=False, indent=2
    )

    prompt = f"""以下是 {date_str} 從 PubMed 抓取的最新迷幻研究（psychedelic research）文獻（共 {paper_count} 篇）。

請進行以下分析，並以 JSON 格式回傳（不要用 markdown code block）：

{{
  "date": "{date_str}",
  "market_summary": "1-2句話總結今天文獻的整體趨勢與亮點",
  "top_picks": [
    {{
      "rank": 1,
      "title_zh": "中文標題",
      "title_en": "English Title",
      "journal": "期刊名",
      "summary": "一句話總結（繁體中文，點出核心發現與臨床意義）",
      "pico": {{
        "population": "研究對象",
        "intervention": "介入措施",
        "comparison": "對照組",
        "outcome": "主要結果"
      }},
      "clinical_utility": "高/中/低",
      "utility_reason": "為什麼實用的一句話說明",
      "tags": ["標籤1", "標籤2"],
      "url": "原文連結",
      "emoji": "相關emoji"
    }}
  ],
  "all_papers": [
    {{
      "title_zh": "中文標題",
      "title_en": "English Title",
      "journal": "期刊名",
      "summary": "一句話總結",
      "clinical_utility": "高/中/低",
      "tags": ["標籤1"],
      "url": "連結",
      "emoji": "emoji"
    }}
  ],
  "keywords": ["關鍵字1", "關鍵字2"],
  "topic_distribution": {{
    "憂鬱症": 3,
    "PTSD": 2
  }}
}}

原始文獻資料：
{papers_text}

請篩選出最重要的 TOP 5-8 篇論文放入 top_picks（按重要性排序），其餘放入 all_papers。
每篇 paper 的 tags 請從以下選擇：憂鬱症、焦慮症、PTSD、強迫症、成癮、慢性疼痛、纖維肌痛、意識研究、神經生物學、心理治療整合、臨床試驗設計、安全性、psilocybin、MDMA、LSD、ketamine、microdosing、迷幻輔助治療、5-HT2A、神經可塑性、主觀經驗、藥理學。
記住：回傳純 JSON，不要用 ```json``` 包裹。"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "top_p": 0.9,
        "max_tokens": 8192,
    }

    models_to_try = [MODEL_NAME, "glm-4-flash", "glm-4"]

    for model in models_to_try:
        payload["model"] = model
        for attempt in range(3):
            try:
                print(
                    f"[INFO] Trying {model} (attempt {attempt + 1})...", file=sys.stderr
                )
                resp = httpx.post(
                    f"{API_BASE}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                if resp.status_code == 429:
                    wait = 60 * (attempt + 1)
                    print(f"[WARN] Rate limited, waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    text = text.rstrip("`").strip()

                result = json.loads(text)
                print(
                    f"[INFO] Analysis complete: {len(result.get('top_picks', []))} top picks, {len(result.get('all_papers', []))} total",
                    file=sys.stderr,
                )
                return result

            except json.JSONDecodeError as e:
                print(
                    f"[WARN] JSON parse failed on attempt {attempt + 1}: {e}",
                    file=sys.stderr,
                )
                if attempt < 2:
                    time.sleep(5)
                continue
            except httpx.HTTPStatusError as e:
                print(
                    f"[ERROR] HTTP {e.response.status_code}: {e.response.text[:200]}",
                    file=sys.stderr,
                )
                if e.response.status_code == 429:
                    wait = 60 * (attempt + 1)
                    time.sleep(wait)
                    continue
                break
            except Exception as e:
                print(f"[ERROR] {model} failed: {e}", file=sys.stderr)
                break

    print("[ERROR] All models and attempts failed", file=sys.stderr)
    return None


def generate_html(analysis: dict, date_str: str) -> str:
    top_picks = analysis.get("top_picks", [])
    all_papers = analysis.get("all_papers", [])
    keywords = analysis.get("keywords", [])
    summary = analysis.get("market_summary", "")
    topic_dist = analysis.get("topic_distribution", {})

    total_papers = len(top_picks) + len(all_papers)

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = ["一", "二", "三", "四", "五", "六", "日"][d.weekday()]
        date_display = f"{d.year}年{d.month}月{d.day}日（週{weekday}）"
    except Exception:
        date_display = date_str

    top_picks_html = ""
    for paper in top_picks:
        rank = paper.get("rank", 0)
        emoji = paper.get("emoji", "🔬")
        title_zh = paper.get("title_zh", "")
        title_en = paper.get("title_en", "")
        journal = paper.get("journal", "")
        summary_text = paper.get("summary", "")
        pico = paper.get("pico", {})
        clinical_utility = paper.get("clinical_utility", "中")
        utility_reason = paper.get("utility_reason", "")
        tags = paper.get("tags", [])
        url = paper.get("url", "")

        pico_html = ""
        if pico:
            pico_html = f"""<div class="pico-grid">
<div class="pico-item"><span class="pico-label">P</span><span class="pico-text">{pico.get("population", "")}</span></div>
<div class="pico-item"><span class="pico-label">I</span><span class="pico-text">{pico.get("intervention", "")}</span></div>
<div class="pico-item"><span class="pico-label">C</span><span class="pico-text">{pico.get("comparison", "")}</span></div>
<div class="pico-item"><span class="pico-label">O</span><span class="pico-text">{pico.get("outcome", "")}</span></div>
</div>"""

        tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
        utility_color = {"高": "#4CAF50", "中": "#F59E0B", "低": "#78909C"}.get(
            clinical_utility, "#78909C"
        )

        top_picks_html += f"""<div class="news-card featured">
<div class="card-header">
<span class="rank-badge">#{rank}</span>
<span class="card-emoji">{emoji}</span>
<h3>{title_zh}</h3>
<p class="title-en">{title_en}</p>
</div>
<p class="card-summary">{summary_text}</p>
{pico_html}
<div class="card-footer">
<span class="tag utility-tag" style="color:{utility_color};border-color:{utility_color}40;background:{utility_color}15">{clinical_utility}實用性</span>
{tags_html}
{"<p class='utility-reason'>" + utility_reason + "</p>" if utility_reason else ""}
{"<a href='" + url + "' target='_blank'>→ PubMed</a>" if url else ""}
</div>
</div>
"""

    all_papers_html = ""
    for paper in all_papers:
        emoji = paper.get("emoji", "📄")
        title_zh = paper.get("title_zh", "")
        title_en = paper.get("title_en", "")
        journal = paper.get("journal", "")
        summary_text = paper.get("summary", "")
        clinical_utility = paper.get("clinical_utility", "中")
        tags = paper.get("tags", [])
        url = paper.get("url", "")

        tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
        utility_color = {"高": "#4CAF50", "中": "#F59E0B", "低": "#78909C"}.get(
            clinical_utility, "#78909C"
        )

        all_papers_html += f"""<div class="news-card">
<h3><span class="card-emoji-sm">{emoji}</span> {title_zh}</h3>
<p class="title-en-sm">{title_en}</p>
<p class="card-summary">{summary_text}</p>
<div class="card-footer">
<span class="tag utility-tag" style="color:{utility_color};border-color:{utility_color}40;background:{utility_color}15">{clinical_utility}</span>
{tags_html}
{"<a href='" + url + "' target='_blank'>→ PubMed</a>" if url else ""}
</div>
</div>
"""

    topic_bars = ""
    if topic_dist:
        max_count = max(topic_dist.values()) if topic_dist else 1
        for topic, count in sorted(topic_dist.items(), key=lambda x: -x[1]):
            pct = int(count / max_count * 100)
            topic_bars += f"""<div class="bar-row">
<span class="bar-label">{topic}</span>
<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>
<span class="bar-count">{count}</span>
</div>
"""

    keywords_html = "".join(f'<span class="keyword">#{k}</span>' for k in keywords)

    summary_list_items = ""
    if summary:
        for s in summary.split("。"):
            s = s.strip()
            if s:
                summary_list_items += f"<li>{s}</li>\n"

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Psychedelic Brain · 迷幻研究文獻日報 · {date_display}</title>
<meta name="description" content="{date_display} 迷幻研究（Psychedelic Research）最新文獻日報，由 AI 自動分析生成"/>
<meta property="og:title" content="Psychedelic Brain · {date_display}"/>
<meta property="og:description" content="迷幻研究每日文獻精選"/>
<meta property="og:type" content="article"/>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🍄</text></svg>"/>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0a0a12; color: #E8E0F0; font-family: -apple-system, "PingFang TC", "Helvetica Neue", Arial, sans-serif; min-height: 100vh; overflow-x: hidden; }}
  body::before {{ content: ''; position: fixed; bottom: -200px; right: -200px; width: 900px; height: 900px; border-radius: 50%; background: radial-gradient(circle, rgba(139,92,246,0.10) 0%, transparent 70%); pointer-events: none; z-index: 0; }}
  body::after {{ content: ''; position: fixed; top: -250px; left: -250px; width: 700px; height: 700px; border-radius: 50%; background: radial-gradient(circle, rgba(6,182,212,0.08) 0%, transparent 70%); pointer-events: none; z-index: 0; }}
  .container {{ position: relative; z-index: 1; max-width: 880px; margin: 0 auto; padding: 60px 32px 80px; }}

  header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 52px; animation: fadeDown 0.6s ease both; }}
  .logo {{ width: 52px; height: 52px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 28px; background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.25); flex-shrink: 0; box-shadow: 0 4px 24px rgba(139,92,246,0.2); }}
  .header-text h1 {{ font-family: -apple-system, "SF Pro Display", sans-serif; font-size: 22px; font-weight: 700; color: #fff; letter-spacing: -0.3px; }}
  .header-meta {{ display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; align-items: center; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; letter-spacing: 0.3px; }}
  .badge-date {{ background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.3); color: #A78BFA; }}
  .badge-count {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); color: #90A4AE; }}
  .badge-source {{ background: transparent; color: #546E7A; font-size: 11px; padding: 0 4px; }}

  .summary-card {{ background: rgba(139,92,246,0.05); border: 1px solid rgba(139,92,246,0.15); border-radius: 20px; padding: 28px 32px; margin-bottom: 32px; animation: fadeUp 0.5s ease 0.1s both; }}
  .summary-card h2 {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.6px; color: #A78BFA; margin-bottom: 16px; }}
  .summary-list {{ list-style: none; display: flex; flex-direction: column; gap: 10px; }}
  .summary-list li {{ font-size: 14px; line-height: 1.7; color: #D4C8E8; padding-left: 18px; position: relative; }}
  .summary-list li::before {{ content: '\\203A'; position: absolute; left: 0; color: #A78BFA; font-weight: 700; font-size: 16px; line-height: 1.4; }}

  .section {{ margin-bottom: 36px; animation: fadeUp 0.5s ease both; }}
  .section-title {{ display: flex; align-items: center; gap: 10px; font-family: -apple-system, "SF Pro Display", sans-serif; font-size: 17px; font-weight: 700; color: #fff; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.07); }}
  .section-icon {{ width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }}

  .news-card {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07); border-radius: 16px; padding: 22px 26px; margin-bottom: 12px; transition: background 0.2s, border-color 0.2s, transform 0.2s; }}
  .news-card:hover {{ background: rgba(139,92,246,0.05); border-color: rgba(139,92,246,0.2); transform: translateY(-2px); }}
  .news-card.featured {{ border-left: 3px solid #8B5CF6; }}
  .news-card h3 {{ font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 6px; }}
  .card-emoji {{ font-size: 16px; margin-right: 4px; }}
  .card-emoji-sm {{ font-size: 14px; }}
  .title-en {{ font-size: 12px; color: #78909C; font-style: italic; margin-bottom: 10px; }}
  .title-en-sm {{ font-size: 11px; color: #78909C; font-style: italic; margin-bottom: 8px; }}
  .card-summary {{ font-size: 13.5px; line-height: 1.75; color: #90A4AE; }}
  .card-footer {{ margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
  .tag {{ padding: 2px 9px; background: rgba(139,92,246,0.10); border-radius: 6px; font-size: 11px; color: #A78BFA; }}
  .utility-tag {{ border: 1px solid; }}
  .utility-reason {{ width: 100%; font-size: 12px; color: #78909C; margin-top: 4px; font-style: italic; }}
  .news-card a {{ font-size: 12px; color: #22D3EE; text-decoration: none; opacity: 0.7; margin-left: auto; }}
  .news-card a:hover {{ opacity: 1; }}
  .rank-badge {{ display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 6px; background: rgba(139,92,246,0.2); color: #A78BFA; font-size: 12px; font-weight: 700; margin-right: 8px; }}

  .pico-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin: 12px 0; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 10px; border: 1px solid rgba(255,255,255,0.05); }}
  .pico-item {{ display: flex; align-items: flex-start; gap: 8px; }}
  .pico-label {{ display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 6px; background: rgba(6,182,212,0.15); color: #22D3EE; font-size: 11px; font-weight: 700; flex-shrink: 0; }}
  .pico-text {{ font-size: 12px; color: #90A4AE; line-height: 1.5; }}

  .bar-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
  .bar-label {{ min-width: 80px; font-size: 12px; color: #90A4AE; text-align: right; }}
  .bar-track {{ flex: 1; height: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: linear-gradient(90deg, #8B5CF6, #06B6D4); border-radius: 4px; transition: width 0.6s ease; }}
  .bar-count {{ min-width: 24px; font-size: 12px; color: #A78BFA; font-weight: 600; }}

  .keywords-section {{ margin-bottom: 36px; }}
  .keywords {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
  .keyword {{ padding: 5px 14px; background: rgba(139,92,246,0.07); border: 1px solid rgba(139,92,246,0.18); border-radius: 20px; font-size: 12px; color: #A78BFA; cursor: default; transition: background 0.2s; }}
  .keyword:hover {{ background: rgba(139,92,246,0.15); }}

  .clinic-banner {{ margin: 40px 0 20px; padding: 20px 24px; background: linear-gradient(135deg, rgba(139,92,246,0.08) 0%, rgba(6,182,212,0.08) 100%); border: 1px solid rgba(139,92,246,0.15); border-radius: 16px; text-align: center; animation: fadeUp 0.5s ease 0.45s both; }}
  .clinic-banner a {{ color: #22D3EE; text-decoration: none; font-size: 15px; font-weight: 600; }}
  .clinic-banner a:hover {{ color: #A78BFA; }}
  .clinic-banner p {{ font-size: 12px; color: #78909C; margin-top: 6px; }}

  footer {{ margin-top: 40px; padding-top: 22px; border-top: 1px solid rgba(255,255,255,0.06); font-size: 11.5px; color: #37474F; display: flex; justify-content: space-between; animation: fadeUp 0.5s ease 0.5s both; }}
  footer a {{ color: #546E7A; text-decoration: none; }}
  footer a:hover {{ color: #A78BFA; }}

  @keyframes fadeDown {{ from {{ opacity: 0; transform: translateY(-16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  @keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  @media (max-width: 600px) {{ .container {{ padding: 36px 18px 60px; }} .summary-card, .news-card {{ padding: 20px 18px; }} footer {{ flex-direction: column; gap: 6px; text-align: center; }} .pico-grid {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">🍄</div>
    <div class="header-text">
      <h1>Psychedelic Brain · 迷幻研究文獻日報</h1>
      <div class="header-meta">
        <span class="badge badge-date">{date_display}</span>
        <span class="badge badge-count">{total_papers} 篇文獻</span>
        <span class="badge badge-source">PubMed + AI Analysis</span>
      </div>
    </div>
  </header>

  {"<div class='summary-card'><h2>今日摘要</h2><ul class='summary-list'>" + summary_list_items + "</ul></div>" if summary_list_items else ""}

  {"<div class='section'><div class='section-title'><div class='section-icon' style='background:rgba(139,92,246,0.15)'>🏆</div>精選 TOP Papers</div>" + top_picks_html + "</div>" if top_picks_html else ""}

  {"<div class='section'><div class='section-title'><div class='section-icon' style='background:rgba(6,182,212,0.15)'>📋</div>其他重要文獻</div>" + all_papers_html + "</div>" if all_papers_html else ""}

  {"<div class='section'><div class='section-title'><div class='section-icon' style='background:rgba(139,92,246,0.10)'>📊</div>主題分布</div>" + topic_bars + "</div>" if topic_bars else ""}

  {"<div class='keywords-section'><div class='section-title'><div class='section-icon' style='background:rgba(139,92,246,0.10)'>#️⃣</div>關鍵詞</div><div class='keywords'>" + keywords_html + "</div></div>" if keywords_html else ""}

  <div class="clinic-banner">
    <a href="{CLINIC_URL}" target="_blank">🧠 力人身心診所 Leepsy Clinic</a>
    <p>專業精神醫學 · 迷幻輔助治療諮詢</p>
  </div>

  <footer>
    <div>Powered by PubMed + Zhipu AI · <a href="https://github.com/u8901006/psychedelic-brain">GitHub</a></div>
    <span>Psychedelic Brain</span>
  </footer>
</div>
</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="Generate psychedelic daily report")
    parser.add_argument("--input", required=True, help="Input papers JSON file")
    parser.add_argument("--output", required=True, help="Output HTML file")
    parser.add_argument("--api-key", default="", help="Zhipu API key")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        print("[ERROR] No API key provided", file=sys.stderr)
        sys.exit(1)

    papers_data = load_papers(args.input)
    date_str = papers_data.get(
        "date", datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    )

    if papers_data.get("count", 0) == 0:
        print("[WARN] No papers found, generating empty report", file=sys.stderr)
        analysis = {
            "date": date_str,
            "market_summary": "今日未找到新的迷幻研究文獻。",
            "top_picks": [],
            "all_papers": [],
            "keywords": ["psychedelic", "psilocybin", "MDMA", "LSD"],
            "topic_distribution": {},
        }
    else:
        analysis = analyze_papers(api_key, papers_data)
        if not analysis:
            print("[WARN] AI analysis failed, generating basic report", file=sys.stderr)
            papers = papers_data.get("papers", [])
            analysis = {
                "date": date_str,
                "market_summary": f"今日共收錄 {len(papers)} 篇迷幻研究文獻。",
                "top_picks": [
                    {
                        "rank": i + 1,
                        "title_zh": p.get("title", ""),
                        "title_en": p.get("title", ""),
                        "journal": p.get("journal", ""),
                        "summary": p.get("abstract", "")[:200],
                        "clinical_utility": "中",
                        "tags": p.get("keywords", [])[:3],
                        "url": p.get("url", ""),
                        "emoji": "🔬",
                    }
                    for i, p in enumerate(papers[:5])
                ],
                "all_papers": [
                    {
                        "title_zh": p.get("title", ""),
                        "title_en": p.get("title", ""),
                        "journal": p.get("journal", ""),
                        "summary": p.get("abstract", "")[:150],
                        "clinical_utility": "中",
                        "tags": p.get("keywords", [])[:2],
                        "url": p.get("url", ""),
                        "emoji": "📄",
                    }
                    for p in papers[5:]
                ],
                "keywords": ["psychedelic", "psilocybin", "MDMA"],
                "topic_distribution": {},
            }

    html = generate_html(analysis, date_str)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] Report saved to {args.output} ({len(html)} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
