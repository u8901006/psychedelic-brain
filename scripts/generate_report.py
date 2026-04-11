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
        utility_class = {
            "高": "utility-high",
            "中": "utility-mid",
            "低": "utility-low",
        }.get(clinical_utility, "utility-mid")

        top_picks_html += f"""<div class="news-card featured">
<div class="card-header">
<span class="rank-badge">#{rank}</span>
<span class="emoji-icon">{emoji}</span>
<span class="{utility_class}">{clinical_utility}實用性</span>
</div>
<h3>{title_zh}</h3>
<p class="journal-source">{journal} &middot; {title_en}</p>
<p>{summary_text}</p>
{pico_html}
<div class="card-footer">
{tags_html}
{"<a href='" + url + "' target='_blank'>閱讀原文 →</a>" if url else ""}
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
        utility_class = {
            "高": "utility-high",
            "中": "utility-mid",
            "低": "utility-low",
        }.get(clinical_utility, "utility-mid")

        all_papers_html += f"""<div class="news-card">
<div class="card-header-row">
<span class="emoji-sm">{emoji}</span>
<span class="{utility_class} utility-sm">{clinical_utility}</span>
</div>
<h3>{title_zh}</h3>
<p class="journal-source">{journal}</p>
<p>{summary_text}</p>
<div class="card-footer">
{tags_html}
{"<a href='" + url + "' target='_blank'>PubMed →</a>" if url else ""}
</div>
</div>
"""

    topic_bars = ""
    if topic_dist:
        max_count = max(topic_dist.values()) if topic_dist else 1
        for topic, count in sorted(topic_dist.items(), key=lambda x: -x[1]):
            pct = int(count / max_count * 100)
            topic_bars += f"""<div class="topic-row">
<span class="topic-name">{topic}</span>
<div class="topic-bar-bg"><div class="topic-bar" style="width:{pct}%"></div></div>
<span class="topic-count">{count}</span>
</div>
"""

    keywords_html = "".join(f'<span class="keyword">{k}</span>' for k in keywords)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Psychedelic Brain &middot; 迷幻研究文獻日報 &middot; {date_display}</title>
<meta name="description" content="{date_display} 迷幻研究（Psychedelic Research）最新文獻日報，由 AI 自動彙整 PubMed 最新論文"/>
<meta property="og:title" content="Psychedelic Brain &middot; {date_display}"/>
<meta property="og:description" content="迷幻研究每日文獻精選"/>
<meta property="og:type" content="article"/>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🍄</text></svg>"/>
<style>
  :root {{ --bg: #f6f1e8; --surface: #fffaf2; --line: #d8c5ab; --text: #2b2118; --muted: #766453; --accent: #8c4f2b; --accent-soft: #ead2bf; --card-bg: color-mix(in srgb, var(--surface) 92%, white); }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: radial-gradient(circle at top, #fff6ea 0, var(--bg) 55%, #ead8c6 100%); color: var(--text); font-family: "Noto Sans TC", "PingFang TC", "Helvetica Neue", Arial, sans-serif; min-height: 100vh; overflow-x: hidden; }}
  .container {{ position: relative; z-index: 1; max-width: 880px; margin: 0 auto; padding: 60px 32px 80px; }}
  header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 52px; animation: fadeDown 0.6s ease both; }}
  .logo {{ width: 48px; height: 48px; border-radius: 14px; background: var(--accent); display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; box-shadow: 0 4px 20px rgba(140,79,43,0.25); }}
  .header-text h1 {{ font-size: 22px; font-weight: 700; color: var(--text); letter-spacing: -0.3px; }}
  .header-meta {{ display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; align-items: center; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; letter-spacing: 0.3px; }}
  .badge-date {{ background: var(--accent-soft); border: 1px solid var(--line); color: var(--accent); }}
  .badge-count {{ background: rgba(140,79,43,0.06); border: 1px solid var(--line); color: var(--muted); }}
  .badge-source {{ background: transparent; color: var(--muted); font-size: 11px; padding: 0 4px; }}
  .summary-card {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 24px; padding: 28px 32px; margin-bottom: 32px; box-shadow: 0 20px 60px rgba(61,36,15,0.06); animation: fadeUp 0.5s ease 0.1s both; }}
  .summary-card h2 {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.6px; color: var(--accent); margin-bottom: 16px; }}
  .summary-text {{ font-size: 15px; line-height: 1.8; color: var(--text); }}
  .section {{ margin-bottom: 36px; animation: fadeUp 0.5s ease both; }}
  .section-title {{ display: flex; align-items: center; gap: 10px; font-size: 17px; font-weight: 700; color: var(--text); margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }}
  .section-icon {{ width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; background: var(--accent-soft); }}
  .news-card {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 24px; padding: 22px 26px; margin-bottom: 12px; box-shadow: 0 8px 30px rgba(61,36,15,0.04); transition: background 0.2s, border-color 0.2s, transform 0.2s; }}
  .news-card:hover {{ transform: translateY(-2px); box-shadow: 0 12px 40px rgba(61,36,15,0.08); }}
  .news-card.featured {{ border-left: 3px solid var(--accent); }}
  .news-card.featured:hover {{ border-color: var(--accent); }}
  .card-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }}
  .rank-badge {{ background: var(--accent); color: #fff7f0; font-weight: 700; font-size: 12px; padding: 2px 8px; border-radius: 6px; }}
  .emoji-icon {{ font-size: 18px; }}
  .card-header-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .emoji-sm {{ font-size: 14px; }}
  .news-card h3 {{ font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 8px; line-height: 1.5; }}
  .journal-source {{ font-size: 12px; color: var(--accent); margin-bottom: 8px; opacity: 0.8; }}
  .news-card p {{ font-size: 13.5px; line-height: 1.75; color: var(--muted); }}
  .card-footer {{ margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
  .tag {{ padding: 2px 9px; background: var(--accent-soft); border-radius: 999px; font-size: 11px; color: var(--accent); }}
  .news-card a {{ font-size: 12px; color: var(--accent); text-decoration: none; opacity: 0.7; margin-left: auto; }}
  .news-card a:hover {{ opacity: 1; }}
  .utility-high {{ color: #5a7a3a; font-size: 11px; font-weight: 600; padding: 2px 8px; background: rgba(90,122,58,0.1); border-radius: 4px; }}
  .utility-mid {{ color: #9f7a2e; font-size: 11px; font-weight: 600; padding: 2px 8px; background: rgba(159,122,46,0.1); border-radius: 4px; }}
  .utility-low {{ color: var(--muted); font-size: 11px; font-weight: 600; padding: 2px 8px; background: rgba(118,100,83,0.08); border-radius: 4px; }}
  .utility-sm {{ font-size: 10px; }}
  .pico-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; padding: 12px; background: rgba(255,253,249,0.8); border-radius: 14px; border: 1px solid var(--line); }}
  .pico-item {{ display: flex; gap: 8px; align-items: baseline; }}
  .pico-label {{ font-size: 10px; font-weight: 700; color: #fff7f0; background: var(--accent); padding: 2px 6px; border-radius: 4px; flex-shrink: 0; }}
  .pico-text {{ font-size: 12px; color: var(--muted); line-height: 1.4; }}
  .topic-section {{ margin-bottom: 36px; }}
  .topic-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
  .topic-name {{ font-size: 13px; color: var(--muted); width: 100px; flex-shrink: 0; text-align: right; }}
  .topic-bar-bg {{ flex: 1; height: 8px; background: var(--line); border-radius: 4px; overflow: hidden; }}
  .topic-bar {{ height: 100%; background: linear-gradient(90deg, var(--accent), #c47a4a); border-radius: 4px; transition: width 0.6s ease; }}
  .topic-count {{ font-size: 12px; color: var(--accent); width: 24px; }}
  .keywords-section {{ margin-bottom: 36px; }}
  .keywords {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
  .keyword {{ padding: 5px 14px; background: var(--accent-soft); border: 1px solid var(--line); border-radius: 20px; font-size: 12px; color: var(--accent); cursor: default; transition: background 0.2s; }}
  .keyword:hover {{ background: rgba(140,79,43,0.18); }}
  .clinic-banner {{ margin-top: 48px; animation: fadeUp 0.5s ease 0.4s both; }}
  .clinic-link {{ display: flex; align-items: center; gap: 14px; padding: 18px 24px; background: var(--card-bg); border: 1px solid var(--line); border-radius: 24px; text-decoration: none; color: var(--text); transition: all 0.2s; box-shadow: 0 8px 30px rgba(61,36,15,0.04); }}
  .clinic-link:hover {{ border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 12px 40px rgba(61,36,15,0.08); }}
  .clinic-icon {{ font-size: 28px; flex-shrink: 0; }}
  .clinic-name {{ font-size: 15px; font-weight: 700; color: var(--text); flex: 1; }}
  .clinic-arrow {{ font-size: 18px; color: var(--accent); font-weight: 700; }}
  footer {{ margin-top: 32px; padding-top: 22px; border-top: 1px solid var(--line); font-size: 11.5px; color: var(--muted); display: flex; justify-content: space-between; animation: fadeUp 0.5s ease 0.5s both; }}
  footer a {{ color: var(--muted); text-decoration: none; }}
  footer a:hover {{ color: var(--accent); }}
  @keyframes fadeDown {{ from {{ opacity: 0; transform: translateY(-16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  @keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  @media (max-width: 600px) {{ .container {{ padding: 36px 18px 60px; }} .summary-card, .news-card {{ padding: 20px 18px; }} .pico-grid {{ grid-template-columns: 1fr; }} footer {{ flex-direction: column; gap: 6px; text-align: center; }} .topic-name {{ width: 70px; font-size: 11px; }} }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">🍄</div>
    <div class="header-text">
      <h1>Psychedelic Brain &middot; 迷幻研究文獻日報</h1>
      <div class="header-meta">
        <span class="badge badge-date">📅 {date_display}</span>
        <span class="badge badge-count">📊 {total_papers} 篇文獻</span>
        <span class="badge badge-source">Powered by PubMed + Zhipu AI</span>
      </div>
    </div>
  </header>

  {"<div class='summary-card'><h2>📋 今日文獻趨勢</h2><p class='summary-text'>" + summary + "</p></div>" if summary else ""}

  {"<div class='section'><div class='section-title'><span class='section-icon'>⭐</span>今日精選 TOP Picks</div>" + top_picks_html + "</div>" if top_picks_html else ""}

  {"<div class='section'><div class='section-title'><span class='section-icon'>📚</span>其他值得關注的文獻</div>" + all_papers_html + "</div>" if all_papers_html else ""}

  {"<div class='topic-section section'><div class='section-title'><span class='section-icon'>📊</span>主題分佈</div>" + topic_bars + "</div>" if topic_bars else ""}

  {"<div class='keywords-section section'><div class='section-title'><span class='section-icon'>🏷️</span>關鍵字</div><div class='keywords'>" + keywords_html + "</div></div>" if keywords_html else ""}

  <div class="clinic-banner">
    <a href="{CLINIC_URL}" class="clinic-link" target="_blank">
      <span class="clinic-icon">🏥</span>
      <span class="clinic-name">李政洋身心診所首頁</span>
      <span class="clinic-arrow">→</span>
    </a>
  </div>

  <footer>
    <span>資料來源：PubMed &middot; 分析模型：glm-4-plus</span>
    <span><a href="https://github.com/u8901006/psychedelic-brain">GitHub</a></span>
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
