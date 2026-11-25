"""Read-only web viewer for Stocky's SQLite database.

Security guarantees:
  * Opens investors_eye.db with SQLite `mode=ro` and `PRAGMA query_only=ON`.
  * Binds only to 127.0.0.1.
  * No write endpoints and no arbitrary SQL endpoint.
  * Credential columns are never selected or rendered.
"""

from __future__ import annotations

import html
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

DB_PATH = Path("/Users/rishavsingla/stocky/backend/investors_eye.db")
HOST = "127.0.0.1"
PORT = 8011

SENSITIVE_COLUMNS = {
    "password",
    "hashed_password",
    "salt",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "request_token",
    "api_key",
    "api_secret",
    "authorization",
}

app = FastAPI(title="Stocky SQLite Viewer", docs_url=None, redoc_url=None)


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def is_sensitive(column: str) -> bool:
    lowered = column.lower()
    return any(part in lowered for part in SENSITIVE_COLUMNS)


def table_names(con: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]


def columns_for(con: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return list(con.execute(f"PRAGMA table_info({ident(table)})"))


def safe_columns(cols: list[sqlite3.Row]) -> list[str]:
    return [row["name"] for row in cols if not is_sensitive(row["name"])]


def row_count(con: sqlite3.Connection, table: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {ident(table)}").fetchone()[0])


def format_cell(value: Any) -> str:
    if value is None:
        return '<span class="null">NULL</span>'
    if isinstance(value, bytes):
        return f'<span class="muted">&lt;binary {len(value)} bytes&gt;</span>'
    if isinstance(value, bool):
        return "true" if value else "false"

    text = str(value)
    if len(text) > 180:
        short = text[:177] + "…"
        return f'<span title="{esc(text)}">{esc(short)}</span>'
    return esc(text)


def render_layout(*, active_table: str, sidebar: str, content: str, summary: dict[str, str], sub_note: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stocky DB Viewer</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 64 64%22><rect width=%2264%22 height=%2264%22 rx=%2214%22 fill=%22%2359c2ff%22/><text x=%2210%22 y=%2244%22 font-size=%2232%22 font-family=%22Arial%22 font-weight=%22bold%22 fill=%22%2308101d%22>IE</text></svg>">
<style>
  :root {{
    --bg: #080c14; --panel: #0f1624; --panel2: #131d2e; --line: #22304a;
    --text: #e8eef7; --muted: #8fa1bb; --accent: #59c2ff; --green: #43d9a3;
    --amber: #ffc857; --red: #ff7a90;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: radial-gradient(1200px 600px at 20% -10%, #15243b 0%, var(--bg) 55%); color: var(--text); font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  a {{ color: inherit; text-decoration: none; }}
  .shell {{ display: grid; grid-template-columns: 270px 1fr; min-height: 100vh; }}
  .sidebar {{ border-right: 1px solid var(--line); background: rgba(15,22,36,.92); padding: 22px 18px; position: sticky; top: 0; height: 100vh; overflow: auto; }}
  .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 750; font-size: 17px; letter-spacing: .2px; }}
  .brand .mark {{ width: 34px; height: 34px; display: grid; place-items: center; border-radius: 10px; background: linear-gradient(135deg, var(--accent), #7b6cff); color: #06101d; font-weight: 900; }}
  .badge {{ display: inline-flex; align-items: center; gap: 6px; margin-top: 18px; padding: 5px 9px; border: 1px solid #245a4a; background: #102b25; color: var(--green); border-radius: 999px; font-size: 11px; font-weight: 700; }}
  .badge::before {{ content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 9px var(--green); }}
  .section-title {{ margin: 24px 0 8px; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }}
  .table-link {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; border-radius: 9px; color: #cbd7e8; }}
  .table-link:hover {{ background: var(--panel2); }}
  .table-link.active {{ background: linear-gradient(90deg, #17324d, #122235); color: #fff; box-shadow: inset 2px 0 0 var(--accent); }}
  .table-link small {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
  .main {{ padding: 28px 34px 60px; min-width: 0; }}
  .head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; flex-wrap: wrap; }}
  h1 {{ margin: 0; font-size: 26px; letter-spacing: -.4px; }}
  .sub {{ color: var(--muted); margin-top: 5px; }}
  .path {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: #a9b9d0; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 22px 0; }}
  .card {{ background: linear-gradient(160deg, var(--panel2), var(--panel)); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }}
  .card .k {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .09em; font-weight: 750; }}
  .card .v {{ margin-top: 5px; font-size: 20px; font-weight: 780; font-variant-numeric: tabular-nums; }}
  .panel {{ background: rgba(15,22,36,.86); border: 1px solid var(--line); border-radius: 16px; overflow: hidden; margin-top: 18px; }}
  .panel-head {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 15px 18px; border-bottom: 1px solid var(--line); background: rgba(19,29,46,.75); flex-wrap: wrap; }}
  .panel-head h2 {{ margin: 0; font-size: 16px; }}
  .panel-body {{ padding: 18px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .07em; padding: 9px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid rgba(34,48,74,.65); vertical-align: top; max-width: 340px; overflow-wrap: anywhere; }}
  tr:last-child td {{ border-bottom: 0; }}
  tbody tr:hover {{ background: rgba(89,194,255,.045); }}
  .null {{ color: #62748e; font-style: italic; }}
  .muted {{ color: var(--muted); }}
  .lock {{ color: var(--amber); font-weight: 700; }}
  .pill {{ display: inline-block; padding: 2px 7px; border-radius: 999px; background: #1c2a41; color: #b9cbe3; font-size: 11px; }}
  .pill.green {{ background: #123b31; color: var(--green); }}
  .pill.amber {{ background: #3b3218; color: var(--amber); }}
  input[type=search] {{ width: 260px; max-width: 100%; padding: 8px 11px; border-radius: 9px; border: 1px solid var(--line); background: #0a111d; color: var(--text); outline: none; }}
  input[type=search]:focus {{ border-color: var(--accent); }}
  .pager {{ display: flex; gap: 8px; align-items: center; justify-content: flex-end; margin-top: 14px; flex-wrap: wrap; }}
  .pager a, .pager span {{ padding: 6px 11px; border: 1px solid var(--line); border-radius: 8px; color: #cbd7e8; background: var(--panel); }}
  .pager .disabled {{ opacity: .38; pointer-events: none; }}
  .note {{ color: var(--muted); font-size: 12px; margin-top: 10px; }}
  .empty {{ padding: 28px; text-align: center; color: var(--muted); }}
  @media (max-width: 820px) {{ .shell {{ grid-template-columns: 1fr; }} .sidebar {{ position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line); }} .main {{ padding: 20px; }} }}
</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand"><span class="mark">IE</span><span>Investor's EYE<br><small style="color:var(--muted);font-weight:500">SQLite Viewer</small></span></div>
    <div class="badge">Read-only · Localhost</div>
    <div class="section-title">Database</div>
    <div class="path">{esc(str(DB_PATH))}</div>
    <div class="section-title">Tables</div>
    {sidebar}
    <div class="note">Credential columns are never queried or displayed.</div>
  </aside>
  <main class="main">
    <div class="head">
      <div>
        <h1>{esc(active_table)}</h1>
        <div class="sub">Browse schema and rows from the live Stocky SQLite file. {sub_note}</div>
      </div>
      <a class="pill green" href="/?table=user_activities">View activity logs →</a>
    </div>
    <div class="cards">
      <div class="card"><div class="k">Database</div><div class="v">{esc(summary['size'])}</div></div>
      <div class="card"><div class="k">Tables</div><div class="v">{esc(summary['tables'])}</div></div>
      <div class="card"><div class="k">Registered users</div><div class="v">{esc(summary['users'])}</div></div>
      <div class="card"><div class="k">Activity events</div><div class="v">{esc(summary['activities'])}</div></div>
    </div>
    {content}
  </main>
</div>
<script>
(function () {{
  const input = document.getElementById('rowFilter');
  if (!input) return;
  const rows = Array.from(document.querySelectorAll('#dataRows tr'));
  input.addEventListener('input', function () {{
    const q = input.value.trim().toLowerCase();
    rows.forEach(row => {{
      row.style.display = !q || (row.dataset.search || '').includes(q) ? '' : 'none';
    }});
  }});
}})();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index(
    table: str = "users",
    page: int = 1,
    per_page: int = 25,
) -> HTMLResponse:
    per_page = max(10, min(int(per_page), 100))
    page = max(1, int(page))
    sub_note = ""

    with closing(connect()) as con:
        tables = table_names(con)
        if not tables:
            content = '<div class="panel"><div class="empty">No tables found in the database.</div></div>'
            sidebar = ""
            active = "No tables"
        else:
            active = table if table in tables else tables[0]
            counts = {name: row_count(con, name) for name in tables}
            sidebar_links = []
            for name in tables:
                css = "table-link active" if name == active else "table-link"
                sidebar_links.append(
                    f'<a class="{css}" href="/?table={esc(name)}">'
                    f'<span>{esc(name)}</span><small>{counts[name]}</small></a>'
                )
            sidebar = "".join(sidebar_links)

            cols = columns_for(con, active)
            visible_cols = safe_columns(cols)
            total = counts[active]
            total_pages = max(1, math.ceil(total / per_page))
            page = min(page, total_pages)
            offset = (page - 1) * per_page

            schema_rows = []
            for idx, col in enumerate(cols):
                name = col["name"]
                hidden = is_sensitive(name)
                visibility = (
                    '<span class="lock">🔒 Hidden</span>'
                    if hidden
                    else '<span class="pill green">Visible</span>'
                )
                schema_rows.append(
                    "<tr>"
                    f"<td>{idx}</td>"
                    f"<td><strong>{esc(name)}</strong></td>"
                    f"<td class='muted'>{esc(col['type'])}</td>"
                    f"<td>{'YES' if col['notnull'] else 'NO'}</td>"
                    f"<td>{'PK' if col['pk'] else '—'}</td>"
                    f"<td class='muted'>{esc(col['dflt_value'])}</td>"
                    f"<td>{visibility}</td>"
                    "</tr>"
                )

            if visible_cols:
                select_sql = ", ".join(ident(c) for c in visible_cols)
                rows = list(
                    con.execute(
                        f"SELECT {select_sql} FROM {ident(active)} ORDER BY rowid DESC LIMIT ? OFFSET ?",
                        (per_page, offset),
                    )
                )
                data_rows = []
                for row in rows:
                    cells = []
                    search_parts = []
                    for c in visible_cols:
                        val = row[c]
                        cells.append(f"<td>{format_cell(val)}</td>")
                        if val is not None:
                            search_parts.append(str(val).lower())
                    data_rows.append(
                        f'<tr data-search="{esc(" | ".join(search_parts))}">' + "".join(cells) + "</tr>"
                    )

                headers = "".join(f"<th>{esc(c)}</th>" for c in visible_cols)
                pager = []
                prev_page = max(1, page - 1)
                next_page = min(total_pages, page + 1)
                pager.append(
                    f'<a class="{"disabled" if page <= 1 else ""}" href="/?table={esc(active)}&page={prev_page}&per_page={per_page}">← Previous</a>'
                )
                pager.append(f'<span>Page {page} of {total_pages}</span>')
                pager.append(
                    f'<a class="{"disabled" if page >= total_pages else ""}" href="/?table={esc(active)}&page={next_page}&per_page={per_page}">Next →</a>'
                )
                data_panel = f"""
                <section class="panel">
                  <div class="panel-head">
                    <h2>Rows <span class="pill">{total}</span></h2>
                    <input id="rowFilter" type="search" placeholder="Filter visible rows…">
                  </div>
                  <div class="panel-body">
                    <table>
                      <thead><tr>{headers}</tr></thead>
                      <tbody id="dataRows">{''.join(data_rows) or f'<tr><td colspan="{len(visible_cols)}" class="empty">No rows</td></tr>'}</tbody>
                    </table>
                    <div class="pager">{''.join(pager)}</div>
                  </div>
                </section>"""
            else:
                data_panel = '<section class="panel"><div class="empty">All columns in this table are hidden for safety.</div></section>'

            content = f"""
            <section class="panel">
              <div class="panel-head"><h2>Columns</h2><span class="pill amber">{len(cols)} total · {len(visible_cols)} visible</span></div>
              <div class="panel-body">
                <table>
                  <thead><tr><th>#</th><th>Column</th><th>Type</th><th>Nullable</th><th>Key</th><th>Default</th><th>Visibility</th></tr></thead>
                  <tbody>{''.join(schema_rows)}</tbody>
                </table>
              </div>
            </section>
            {data_panel}"""

            last_activity = con.execute(
                "SELECT MAX(created_at) FROM user_activities"
            ).fetchone()[0]
            users_count = counts.get("users", 0)
            activity_count = counts.get("user_activities", 0)
            size = f"{DB_PATH.stat().st_size / 1024:.1f} KB"
            summary = {
                "size": size,
                "tables": str(len(tables)),
                "users": str(users_count),
                "activities": str(activity_count),
            }
            if last_activity:
                sub_note = f"<span class='pill'>Last activity: {esc(str(last_activity))}</span>"

    return HTMLResponse(render_layout(
        active_table=active,
        sidebar=sidebar,
        content=content,
        summary=summary,
        sub_note=sub_note,
    ))


if __name__ == "__main__":
    import uvicorn

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
