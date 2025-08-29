#!/usr/bin/env python3
"""
Build statistics.html from publications.json.

Reads the consolidated publications JSON, computes aggregations
(by venue, year, body part, table type), and writes an HTML fragment
with embedded Chart.js doughnut/bar charts.
"""

from __future__ import annotations
from pathlib import Path
import json
import re
from collections import Counter
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
TABLES_DIR = ROOT / "tables"
TABLES_DIR.mkdir(exist_ok=True)
JSON_FILE = ROOT / "assets" / "data" / "publications.json"

# Lively pastel palette (colorblind-safe)
COLORS = [
    "#7EB8DA",  # sky blue
    "#F4A7B9",  # pink
    "#A8D8A8",  # mint green
    "#F7C873",  # golden yellow
    "#C3A6D8",  # lavender
    "#F9B97A",  # peach
    "#87CEEB",  # light sky
    "#E8A0BF",  # rose
    "#B5D99C",  # pistachio
    "#FFD699",  # apricot
    "#C4C4C4",  # light grey (for "Other")
]


def _normalize_body_part(raw: str) -> str:
    """Extract primary body-part category from Contents field."""
    if not raw:
        return ""
    s = re.sub(r"\([^)]*\)", "", raw).strip()
    parts = re.split(r"[,/;]|\s\+\s", s)
    for part in parts:
        lower = part.lower().strip()
        if not lower:
            continue
        if lower in ("head", "head only", "portrait") or lower.startswith("head "):
            return "Face"
        if lower in (
            "full body", "full-body", "body", "upper body",
            "full body (clothed)", "full-body (clothed)",
        ):
            return "Full-body"
        if lower == "face":
            return "Face"
        if lower in ("hands", "hand"):
            return "Hands"
        if lower == "hair":
            return "Hair"
        if lower in ("garment", "garments", "clothing"):
            return "Garment"
        if lower == "teeth":
            return "Teeth"
        if lower == "tongue":
            return "Tongue"
    return ""


def build_statistics_page():
    if not JSON_FILE.exists():
        print(f"  publications.json not found at {JSON_FILE}, skipping statistics.")
        return

    with JSON_FILE.open("r", encoding="utf-8") as f:
        entries: List[Dict] = json.load(f)

    total = len(entries)

    # --- Aggregation: by venue (top 10 + Other) ---
    venue_counter: Counter = Counter()
    for e in entries:
        v = e.get("venue", "").strip()
        if v:
            venue_counter[v] += 1
        else:
            venue_counter["Unknown"] += 1

    top_venues = venue_counter.most_common(10)
    other_count = sum(venue_counter.values()) - sum(c for _, c in top_venues)
    venue_labels = [v for v, _ in top_venues]
    venue_data = [c for _, c in top_venues]
    if other_count > 0:
        venue_labels.append("Other")
        venue_data.append(other_count)

    # --- Aggregation: by year ---
    year_counter: Counter = Counter()
    for e in entries:
        y = e.get("year", "").strip()
        if y:
            year_counter[y] += 1

    year_labels = sorted(year_counter.keys())
    year_data = [year_counter[y] for y in year_labels]

    # --- Aggregation: by body part ---
    body_counter: Counter = Counter()
    for e in entries:
        cls = e.get("classification")
        if cls and cls.get("fields"):
            contents = cls["fields"].get("Contents", "")
            part = _normalize_body_part(contents)
            if part:
                body_counter[part] += 1
            else:
                body_counter["Other"] += 1
        else:
            body_counter["Unclassified"] += 1

    body_labels = sorted(body_counter.keys(), key=lambda x: -body_counter[x])
    body_data = [body_counter[b] for b in body_labels]

    # --- Aggregation: avatar vs assets ---
    type_counter: Counter = Counter()
    for e in entries:
        cls = e.get("classification")
        if cls:
            tt = cls.get("table_type", "unclassified")
            type_counter[tt.capitalize()] += 1
        elif e.get("skip_reason"):
            type_counter["Not classified"] += 1
        else:
            type_counter["Unclassified"] += 1

    type_labels = sorted(type_counter.keys(), key=lambda x: -type_counter[x])
    type_data = [type_counter[t] for t in type_labels]

    # --- Build HTML ---
    html_parts: List[str] = []

    html_parts.append('<div class="stats-container">')
    html_parts.append(f'  <div class="stats-header"><span class="stats-total">{total} publications analyzed</span></div>')

    # Grid of 4 chart cards
    html_parts.append('  <div class="stats-grid">')

    charts = [
        ("venueChart", "Publications by Venue",
         f"Distribution of {total} publications across the top 10 most frequent venues. "
         f"CVPR dominates with {venue_data[0]} papers, followed by "
         f"{venue_labels[1]} ({venue_data[1]}) and {venue_labels[2]} ({venue_data[2]})."),
        ("bodyChart", "Publications by Body Part",
         "Breakdown by primary body region addressed. "
         f"Full-body ({body_data[body_labels.index('Full-body')]}) and "
         f"Face ({body_data[body_labels.index('Face')]}) are the most studied regions."),
        ("typeChart", "Avatar vs Assets",
         f"Classification into avatar methods ({type_data[type_labels.index('Avatar')]}) "
         f"and asset generation ({type_data[type_labels.index('Assets')]}). "
         f"{type_data[type_labels.index('Not classified')]} papers were not classified."),
        ("yearChart", "Publications by Year",
         f"Number of publications per year from {year_labels[0]} to {year_labels[-1]}. "
         f"The field has seen rapid growth, peaking at {max(year_data)} papers in "
         f"{year_labels[year_data.index(max(year_data))]}."),
    ]

    for chart_id, title, caption in charts:
        html_parts.append('    <div class="stats-card">')
        html_parts.append(f'      <h3 class="stats-card-title">{title}</h3>')
        html_parts.append(f'      <div class="stats-canvas-wrap"><canvas id="{chart_id}" aria-label="{title}"></canvas></div>')
        html_parts.append(f'      <p class="stats-caption">{caption}</p>')
        html_parts.append('    </div>')

    html_parts.append('  </div>')  # stats-grid
    html_parts.append('</div>')  # stats-container

    # --- Styles ---
    html_parts.append('<style>')
    html_parts.append("""
.stats-container {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
}
.stats-header {
  margin-bottom: 1rem;
}
.stats-total {
  font-size: 0.9rem;
  color: #64748b;
  font-weight: 500;
}
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}
.stats-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.25rem;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}
.stats-card-title {
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  color: #0f172a;
}
.stats-canvas-wrap {
  position: relative;
  width: 100%;
}
.stats-caption {
  font-size: 0.82rem;
  color: #64748b;
  line-height: 1.5;
  margin: 0.75rem 0 0;
  text-align: left;
}
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
""")
    html_parts.append('</style>')

    # --- Single inline script that loads Chart.js dynamically, then creates charts ---
    html_parts.append('<script>')

    # Embed data as JS variables
    data_json = json.dumps({
        "venue": {"labels": venue_labels, "data": venue_data},
        "year": {"labels": year_labels, "data": year_data},
        "body": {"labels": body_labels, "data": body_data},
        "type": {"labels": type_labels, "data": type_data},
    })
    colors_json = json.dumps(COLORS)

    html_parts.append(f"""
(function() {{
  var DATA = {data_json};
  var COLORS = {colors_json};

  function buildCharts() {{
    // Register the datalabels plugin
    Chart.register(ChartDataLabels);

    function colorsForN(n) {{
      var out = [];
      for (var i = 0; i < n; i++) out.push(COLORS[i % COLORS.length]);
      return out;
    }}

    var tooltipOpts = {{
      callbacks: {{
        label: function(ctx) {{
          var total = ctx.dataset.data.reduce(function(a, b) {{ return a + b; }}, 0);
          var pct = ((ctx.parsed || ctx.raw) / total * 100).toFixed(1);
          return ctx.label + ': ' + (ctx.parsed || ctx.raw) + ' (' + pct + '%)';
        }}
      }}
    }};

    // Datalabels config: show label + percentage on each slice
    var datalabelOpts = {{
      color: '#1e293b',
      font: {{ size: 11, weight: '600' }},
      textAlign: 'center',
      formatter: function(value, ctx) {{
        var total = ctx.dataset.data.reduce(function(a, b) {{ return a + b; }}, 0);
        var pct = (value / total * 100).toFixed(1);
        // Hide label if slice is too small (<4%)
        if (value / total < 0.04) return '';
        return ctx.chart.data.labels[ctx.dataIndex] + '\\n' + pct + '%';
      }}
    }};

    var barTooltipOpts = {{
      callbacks: {{
        label: function(ctx) {{
          var total = ctx.dataset.data.reduce(function(a, b) {{ return a + b; }}, 0);
          var val = ctx.parsed.y;
          var pct = (val / total * 100).toFixed(1);
          return val + ' papers (' + pct + '%)';
        }}
      }}
    }};

    function doughnutOpts(labels) {{
      return {{
        responsive: true,
        plugins: {{
          legend: {{ position: 'right', labels: {{ boxWidth: 14, font: {{ size: 12 }} }} }},
          tooltip: tooltipOpts,
          datalabels: datalabelOpts
        }}
      }};
    }}

    new Chart(document.getElementById('venueChart'), {{
      type: 'doughnut',
      data: {{
        labels: DATA.venue.labels,
        datasets: [{{ data: DATA.venue.data, backgroundColor: colorsForN(DATA.venue.labels.length) }}]
      }},
      options: doughnutOpts(DATA.venue.labels)
    }});

    new Chart(document.getElementById('yearChart'), {{
      type: 'bar',
      data: {{
        labels: DATA.year.labels,
        datasets: [{{ label: 'Papers', data: DATA.year.data, backgroundColor: '#7EB8DA', borderRadius: 4 }}]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ display: false }},
          tooltip: barTooltipOpts,
          datalabels: {{ display: false }}
        }},
        scales: {{
          y: {{ beginAtZero: true, ticks: {{ precision: 0 }} }},
          x: {{ grid: {{ display: false }} }}
        }}
      }}
    }});

    new Chart(document.getElementById('bodyChart'), {{
      type: 'doughnut',
      data: {{
        labels: DATA.body.labels,
        datasets: [{{ data: DATA.body.data, backgroundColor: colorsForN(DATA.body.labels.length) }}]
      }},
      options: doughnutOpts(DATA.body.labels)
    }});

    new Chart(document.getElementById('typeChart'), {{
      type: 'doughnut',
      data: {{
        labels: DATA.type.labels,
        datasets: [{{ data: DATA.type.data, backgroundColor: colorsForN(DATA.type.labels.length) }}]
      }},
      options: doughnutOpts(DATA.type.labels)
    }});
  }}

  // Load Chart.js + datalabels plugin, then build charts
  function loadScript(url, cb) {{
    var s = document.createElement('script');
    s.src = url;
    s.onload = cb;
    s.onerror = function() {{ console.error('Failed to load: ' + url); }};
    document.head.appendChild(s);
  }}

  function ensureChartJs(cb) {{
    if (typeof Chart !== 'undefined') return cb();
    loadScript('https://cdn.jsdelivr.net/npm/chart.js', cb);
  }}

  function ensureDatalabels(cb) {{
    if (typeof ChartDataLabels !== 'undefined') return cb();
    loadScript('https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2', cb);
  }}

  ensureChartJs(function() {{
    ensureDatalabels(buildCharts);
  }});
}})();
""")
    html_parts.append('</script>')

    out_path = TABLES_DIR / "statistics.html"
    out_path.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"  Wrote tables/statistics.html ({total} entries, 4 charts)")


def main():
    build_statistics_page()


if __name__ == "__main__":
    main()
