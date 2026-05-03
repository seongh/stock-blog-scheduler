#!/usr/bin/env python3
"""
GitHub Pages 사이트 생성기
outputs/ 폴더의 마크다운 파일을 읽어 docs/ 폴더에 HTML 사이트를 생성합니다.
TradingView 위젯(티커테이프·미니차트·경제달력) 포함
"""
import re
import shutil
from pathlib import Path
from datetime import datetime

try:
    import markdown as md_lib
    USE_MD_LIB = True
except ImportError:
    USE_MD_LIB = False
    print("⚠️  markdown 라이브러리 없음 — 기본 변환 사용")


# ── 포스트 타입 분류 ────────────────────────────────────────────────────────
def get_post_type(filename: str) -> dict:
    if "미국증시" in filename:
        return {"icon": "🌅", "label": "모닝 리포트", "color": "#f59e0b"}
    elif "TOP5" in filename:
        return {"icon": "☀️", "label": "한국 TOP5", "color": "#10b981"}
    elif "저녁" in filename:
        return {"icon": "🌙", "label": "저녁 브리핑", "color": "#6366f1"}
    else:
        return {"icon": "📊", "label": "리포트", "color": "#64748b"}


def extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def md_to_html(content: str) -> str:
    if USE_MD_LIB:
        return md_lib.markdown(
            content,
            extensions=["tables", "fenced_code", "nl2br"],
        )
    lines = content.splitlines()
    result = []
    in_table = False
    for line in lines:
        if line.startswith("# "):
            result.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            result.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            result.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("> "):
            result.append(f"<blockquote><p>{line[2:]}</p></blockquote>")
        elif line.startswith("- ") or line.startswith("* "):
            result.append(f"<li>{line[2:]}</li>")
        elif line.startswith("|"):
            if not in_table:
                result.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            result.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        else:
            if in_table:
                result.append("</table>")
                in_table = False
            if line.strip():
                line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
                line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
                result.append(f"<p>{line}</p>")
    if in_table:
        result.append("</table>")
    return "\n".join(result)


# ── TradingView 위젯 ────────────────────────────────────────────────────────

TV_TICKER = '''<div class="tradingview-widget-container tv-ticker-wrap">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
  {
    "symbols": [
      {"proName":"FOREXCOM:SPXUSD","title":"S&P 500"},
      {"proName":"FOREXCOM:NSXUSD","title":"나스닥 100"},
      {"proName":"DJ:DJI","title":"다우"},
      {"description":"코스피","proName":"KRX:KOSPI"},
      {"description":"코스닥","proName":"KRX:KOSDAQ"},
      {"description":"달러/원","proName":"FX:USDKRW"},
      {"description":"달러인덱스","proName":"CAPITALCOM:DXY"},
      {"description":"미 10년채","proName":"CAPITALCOM:US10Y"},
      {"description":"금","proName":"TVC:GOLD"},
      {"description":"WTI","proName":"TVC:USOIL"},
      {"description":"VIX","proName":"CAPITALCOM:VIX"},
      {"description":"비트코인","proName":"BITSTAMP:BTCUSD"}
    ],
    "showSymbolLogo": true,
    "colorTheme": "light",
    "isTransparent": false,
    "displayMode": "adaptive",
    "locale": "kr"
  }
  </script>
</div>'''


def _mini_chart(symbol: str, color: str) -> str:
    return f'''<div class="tradingview-widget-container">
    <div class="tradingview-widget-container__widget"></div>
    <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
    {{
      "symbol": "{symbol}",
      "width": "100%",
      "height": 200,
      "locale": "kr",
      "dateRange": "1D",
      "colorTheme": "light",
      "trendLineColor": "{color}",
      "underLineColor": "{color}33",
      "underLineBottomColor": "rgba(255,255,255,0)",
      "isTransparent": false,
      "autosize": true,
      "largeChartUrl": "https://www.tradingview.com/chart/?symbol={symbol.replace(":", "%3A")}"
    }}
    </script>
  </div>'''


# 포스트 타입별 차트 설정
CHART_CONFIG = {
    "미국증시": {
        "title": "📊 미국 시장 실시간 차트",
        "symbols": [
            ("FOREXCOM:SPXUSD", "#2563eb"),
            ("FOREXCOM:NSXUSD", "#7c3aed"),
            ("CAPITALCOM:DXY",   "#059669"),
            ("CAPITALCOM:US10Y", "#dc2626"),
            ("CAPITALCOM:VIX",   "#d97706"),
            ("TVC:GOLD",        "#f59e0b"),
        ],
        "calendar": True,
    },
    "TOP5": {
        "title": "📊 한국 시장 실시간 차트",
        "symbols": [
            ("KRX:KOSPI",   "#2563eb"),
            ("KRX:KOSDAQ",  "#7c3aed"),
            ("FX:USDKRW",   "#059669"),
            ("KRX:005930",  "#dc2626"),   # 삼성전자
            ("KRX:000660",  "#d97706"),   # SK하이닉스
            ("KRX:035420",  "#10b981"),   # NAVER
        ],
        "calendar": False,
    },
    "저녁": {
        "title": "📊 마감 & 프리마켓 차트",
        "symbols": [
            ("KRX:KOSPI",       "#2563eb"),
            ("FOREXCOM:SPXUSD", "#7c3aed"),
            ("FX:USDKRW",       "#059669"),
            ("CAPITALCOM:US10Y", "#dc2626"),
            ("CAPITALCOM:VIX",   "#d97706"),
            ("TVC:USOIL",        "#78716c"),
        ],
        "calendar": True,
    },
    "default": {
        "title": "📊 글로벌 시장 차트",
        "symbols": [
            ("FOREXCOM:SPXUSD", "#2563eb"),
            ("KRX:KOSPI",       "#7c3aed"),
            ("FX:USDKRW",       "#059669"),
            ("CAPITALCOM:DXY",   "#dc2626"),
            ("CAPITALCOM:VIX",   "#d97706"),
            ("TVC:GOLD",        "#f59e0b"),
        ],
        "calendar": True,
    },
}

TV_CALENDAR = '''<div class="tv-calendar-wrap">
  <h2 class="section-label">📅 경제지표 캘린더</h2>
  <div class="tradingview-widget-container">
    <div class="tradingview-widget-container__widget"></div>
    <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
    {
      "colorTheme": "light",
      "isTransparent": false,
      "width": "100%",
      "height": 400,
      "locale": "kr",
      "importanceFilter": "0,1",
      "countryFilter": "us,kr,jp,cn,eu"
    }
    </script>
  </div>
</div>'''


def get_tv_blocks(filename: str) -> tuple[str, str]:
    """(chart_html, calendar_html) 반환"""
    key = "default"
    for k in ("미국증시", "TOP5", "저녁"):
        if k in filename:
            key = k
            break
    cfg = CHART_CONFIG[key]

    charts = "".join(
        f'<div class="tv-chart-item">{_mini_chart(sym, color)}</div>'
        for sym, color in cfg["symbols"]
    )
    chart_block = f'''<div class="tv-charts-wrap">
  <h2 class="section-label">{cfg["title"]}</h2>
  <div class="tv-charts-grid">{charts}</div>
</div>'''

    calendar_block = TV_CALENDAR if cfg["calendar"] else ""
    return chart_block, calendar_block


# ── CSS ─────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --bg: #f8fafc;
  --surface: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --muted: #64748b;
  --accent: #2563eb;
  --radius: 12px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── 헤더 ── */
.site-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  position: sticky; top: 0; z-index: 100;
}
.header-inner {
  max-width: 1100px; margin: 0 auto;
  display: flex; align-items: center; gap: 16px;
  height: 56px;
}
.site-logo { font-size: 20px; font-weight: 700; color: var(--text); }
.site-logo span { color: var(--accent); }

/* ── 티커 테이프 ── */
.tv-ticker-wrap {
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

/* ── 인덱스 히어로 ── */
.hero {
  background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
  color: #fff; padding: 48px 24px 40px;
  text-align: center;
}
.hero h1 { font-size: 28px; font-weight: 800; margin-bottom: 8px; }
.hero p { font-size: 15px; opacity: 0.85; }
.stats {
  display: flex; justify-content: center; gap: 32px; margin-top: 24px;
}
.stat { text-align: center; }
.stat-num { font-size: 26px; font-weight: 700; }
.stat-label { font-size: 12px; opacity: 0.75; margin-top: 2px; }

.container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }

/* ── 날짜 섹션 ── */
.date-section { margin-bottom: 32px; }
.date-heading {
  font-size: 13px; font-weight: 600;
  color: var(--muted); letter-spacing: .05em;
  text-transform: uppercase; margin-bottom: 12px;
  padding-bottom: 8px; border-bottom: 1px solid var(--border);
}

/* ── 포스트 카드 ── */
.post-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}
.post-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  transition: box-shadow .15s, transform .15s;
  display: flex; flex-direction: column; gap: 10px;
}
.post-card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,.08);
  transform: translateY(-2px);
}
.post-type {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600;
  padding: 3px 10px; border-radius: 20px;
  border: 1px solid; width: fit-content;
}
.post-title {
  font-size: 14px; font-weight: 600;
  color: var(--text); line-height: 1.4;
}
.post-meta { font-size: 12px; color: var(--muted); }
.read-btn {
  margin-top: auto;
  display: inline-block;
  background: var(--accent); color: #fff;
  padding: 7px 16px; border-radius: 8px;
  font-size: 13px; font-weight: 500;
  text-align: center;
}
.read-btn:hover { background: #1d4ed8; text-decoration: none; }

/* ── 포스트 헤더 ── */
.post-header {
  background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
  color: #fff; padding: 40px 24px 32px;
}
.post-header .breadcrumb {
  font-size: 13px; opacity: .75; margin-bottom: 12px;
}
.post-header h1 { font-size: 24px; font-weight: 800; line-height: 1.35; }
.post-header .meta {
  margin-top: 12px; font-size: 13px; opacity: .8;
  display: flex; gap: 16px; flex-wrap: wrap;
}

/* ── TradingView 차트 섹션 ── */
.tv-charts-wrap {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 24px;
}
.section-label {
  max-width: 1100px; margin: 0 auto 16px;
  font-size: 17px; font-weight: 700; color: var(--text);
  display: flex; align-items: center; gap: 8px;
}
.tv-charts-grid {
  max-width: 1100px; margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.tv-chart-item {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--surface);
}

/* ── 경제달력 섹션 ── */
.tv-calendar-wrap {
  background: var(--surface);
  border-top: 1px solid var(--border);
  padding: 24px;
  margin-top: 32px;
}
.tv-calendar-wrap .section-label {
  margin-bottom: 16px;
}

/* ── 포스트 본문 ── */
.article { max-width: 860px; margin: 0 auto; padding: 32px 24px 48px; }
.article h1 { font-size: 22px; margin: 28px 0 10px; }
.article h2 {
  font-size: 19px; margin: 32px 0 10px;
  padding-bottom: 6px; border-bottom: 2px solid var(--accent);
}
.article h3 { font-size: 16px; margin: 20px 0 8px; color: #374151; }
.article p { margin-bottom: 12px; }
.article li { margin-left: 22px; margin-bottom: 4px; }
.article table {
  width: 100%; border-collapse: collapse;
  margin: 16px 0; font-size: 14px;
}
.article th, .article td {
  padding: 10px 14px;
  border: 1px solid var(--border); text-align: left;
}
.article th { background: #f1f5f9; font-weight: 600; }
.article tr:nth-child(even) { background: #f8fafc; }
.article blockquote {
  border-left: 3px solid var(--accent);
  padding: 10px 16px; margin: 16px 0;
  background: #eff6ff; border-radius: 0 8px 8px 0;
  color: #1e40af; font-size: 14px;
}
.article code {
  background: #f1f5f9; padding: 2px 6px;
  border-radius: 4px; font-size: 13px;
}
.article pre {
  background: #1e293b; color: #e2e8f0;
  padding: 16px; border-radius: 8px;
  overflow-x: auto; margin: 16px 0;
}
.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  color: var(--accent); font-size: 14px; font-weight: 500;
  margin-bottom: 24px;
}
.footer {
  text-align: center; font-size: 12px; color: var(--muted);
  padding: 24px; border-top: 1px solid var(--border);
  margin-top: 40px;
}

@media (max-width: 900px) {
  .tv-charts-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .tv-charts-grid { grid-template-columns: 1fr; }
  .post-grid { grid-template-columns: 1fr; }
  .stats { gap: 20px; }
  .hero h1 { font-size: 22px; }
}
"""


# ── HTML 렌더러 ──────────────────────────────────────────────────────────────

def render_index(posts: list) -> str:
    from collections import defaultdict
    by_date = defaultdict(list)
    for p in posts:
        by_date[p["date"]].append(p)

    total = len(posts)
    dates = sorted(by_date.keys(), reverse=True)

    cards_html = ""
    for date in dates:
        day_posts = by_date[date]
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            weekdays = ["월", "화", "수", "목", "금", "토", "일"]
            display_date = f"{dt.year}년 {dt.month}월 {dt.day}일 ({weekdays[dt.weekday()]})"
        except Exception:
            display_date = date

        cards = ""
        for p in day_posts:
            pt = p["type"]
            cards += f"""
            <div class="post-card">
              <span class="post-type" style="color:{pt['color']};border-color:{pt['color']}20;background:{pt['color']}10">
                {pt['icon']} {pt['label']}
              </span>
              <div class="post-title">{p['title']}</div>
              <div class="post-meta">{display_date}</div>
              <a class="read-btn" href="posts/{p['filename']}">읽기 →</a>
            </div>"""

        cards_html += f"""
        <div class="date-section">
          <div class="date-heading">{display_date}</div>
          <div class="post-grid">{cards}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stock Blog — 주식 시황 리포트</title>
  <style>{CSS}</style>
</head>
<body>
  <header class="site-header">
    <div class="header-inner">
      <span class="site-logo">📊 Stock<span>Blog</span></span>
    </div>
  </header>

  {TV_TICKER}

  <div class="hero">
    <h1>주식 시황 리포트</h1>
    <p>매일 아침·오후·저녁 자동 생성되는 증권사급 분석 블로그</p>
    <div class="stats">
      <div class="stat">
        <div class="stat-num">{total}</div>
        <div class="stat-label">총 리포트</div>
      </div>
      <div class="stat">
        <div class="stat-num">{len(dates)}</div>
        <div class="stat-label">발행일</div>
      </div>
      <div class="stat">
        <div class="stat-num">6</div>
        <div class="stat-label">일일 스케줄</div>
      </div>
    </div>
  </div>

  <div class="container">
    {cards_html if posts else '<p style="color:var(--muted);text-align:center;padding:48px 0">아직 생성된 리포트가 없습니다.</p>'}
  </div>

  <footer class="footer">
    본 블로그는 정보 제공 목적으로 자동 생성됩니다. 투자 판단의 책임은 본인에게 있습니다.
  </footer>
</body>
</html>"""


def render_post(title: str, date_str: str, content: str, filename: str) -> str:
    pt = get_post_type(filename)
    body_html = md_to_html(content)
    chart_block, calendar_block = get_tv_blocks(filename)

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        display_date = f"{dt.year}년 {dt.month}월 {dt.day}일 ({weekdays[dt.weekday()]})"
    except Exception:
        display_date = date_str

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Stock Blog</title>
  <style>{CSS}</style>
</head>
<body>
  <header class="site-header">
    <div class="header-inner">
      <a class="site-logo" href="../index.html">📊 Stock<span>Blog</span></a>
    </div>
  </header>

  {TV_TICKER}

  <div class="post-header">
    <div style="max-width:860px;margin:0 auto">
      <div class="breadcrumb">
        <a href="../index.html" style="color:#93c5fd">← 목록으로</a>
      </div>
      <h1>{title}</h1>
      <div class="meta">
        <span>{pt['icon']} {pt['label']}</span>
        <span>📅 {display_date}</span>
      </div>
    </div>
  </div>

  {chart_block}

  <div class="article">
    <a class="back-link" href="../index.html">← 전체 목록</a>
    {body_html}
    {calendar_block}
  </div>

  <footer class="footer">
    본 글은 정보 제공 목적으로 자동 생성됩니다. 투자 판단의 책임은 본인에게 있습니다.
  </footer>
</body>
</html>"""


# ── 메인 ────────────────────────────────────────────────────────────────────

def generate_site():
    outputs_dir = Path("outputs")
    site_dir = Path("docs")

    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir()
    (site_dir / "posts").mkdir()

    posts = []

    md_files = sorted(
        [f for f in outputs_dir.glob("**/*.md") if f.name != ".gitkeep"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        title = extract_title(content, md_file.stem)
        date_str = md_file.parent.name

        html_filename = re.sub(r"[^\w가-힣-]", "_", md_file.stem) + ".html"
        html_path = site_dir / "posts" / html_filename

        post_html = render_post(title, date_str, content, md_file.stem)
        html_path.write_text(post_html, encoding="utf-8")

        posts.append({
            "title": title,
            "date": date_str,
            "filename": html_filename,
            "type": get_post_type(md_file.stem),
        })

        print(f"  ✅ {md_file.name} → posts/{html_filename}")

    index_html = render_index(posts)
    (site_dir / "index.html").write_text(index_html, encoding="utf-8")

    print(f"\n🌐 사이트 생성 완료: {len(posts)}개 포스트 → docs/")


if __name__ == "__main__":
    generate_site()
