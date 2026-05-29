#!/usr/bin/env python3
"""Build one combined vulnerability dashboard across all Dependency-Track instances.

Reads config.py (COMPANIES) + api_keys.json, queries each instance for its projects,
current metrics and findings, and writes:
    reports/combined_report_latest.json
    reports/combined_report_latest.html

Usage:
    python3 combined_report.py            # just generate the files
    python3 combined_report.py --serve    # generate, then serve on :8090
    python3 combined_report.py --serve 9000
"""
import sys, os, json, html, urllib.request, urllib.error
from datetime import datetime
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
API_URL = "http://localhost:8088"
API_KEY = "odt_eGC3PlT2_eEMAyQbnd6bVvk9Kfvh8Fgx6fmISFbke"
REPORT_DIR = os.path.join(BASE_DIR, "reports")
SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4, "UNASSIGNED": 5}
TOP_N = 5


def api_get(url, api_key):
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, Exception):
        pass
    return None



def collect():
    report = []

    teams = api_get(f"{API_URL}/api/v1/team", API_KEY) or []

    for team in teams:
        team_uuid = team["uuid"]
        team_name = team["name"]

        print(f"Fetching projects for team: {team_name}")

        projects = api_get(
            f"{API_URL}/api/v1/acl/team/{team_uuid}?pageSize=500&pageNumber=1",
            API_KEY
        ) or []

        if not projects:
            continue

        entry = {
            "company_id": team_name,
            "company_name": team_name,
            "api_url": API_URL,
            "frontend_url": API_URL,
            "projects": []
        }

        for p in projects:
            uuid = p["uuid"]

            m = api_get(f"{API_URL}/api/v1/metrics/project/{uuid}/current", API_KEY) or {}
            findings = api_get(f"{API_URL}/api/v1/finding/project/{uuid}", API_KEY) or []

            findings.sort(key=lambda f: SEV_ORDER.get(
                (f.get("vulnerability") or {}).get("severity", "UNASSIGNED"), 9))

            top = []
            for f in findings[:TOP_N]:
                v = f.get("vulnerability") or {}
                top.append({
                    "vulnId": v.get("vulnId"),
                    "severity": v.get("severity"),
                    "source": v.get("source"),
                    "description": (v.get("description") or "")[:220],
                })

            entry["projects"].append({
                "name": p.get("name"),
                "version": p.get("version"),
                "uuid": uuid,
                "description": p.get("description", ""),
                "total_components": m.get("components", 0),
                "total_vulnerabilities": m.get("vulnerabilities", 0),
                "vulnerabilities_by_severity": {
                    "CRITICAL": m.get("critical", 0),
                    "HIGH": m.get("high", 0),
                    "MEDIUM": m.get("medium", 0),
                    "LOW": m.get("low", 0),
                    "UNASSIGNED": m.get("unassigned", 0),
                },
                "risk_score": m.get("inheritedRiskScore", 0),
                "top_vulnerabilities": top,
            })

        report.append(entry)

    return report




def render_html(report):
    companies = len(report)
    projects = sum(len(c["projects"]) for c in report)
    comps = sum(p["total_components"] for c in report for p in c["projects"])
    vulns = sum(p["total_vulnerabilities"] for c in report for p in c["projects"])
    sev_tot = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNASSIGNED": 0}
    for c in report:
        for p in c["projects"]:
            for s, n in p["vulnerabilities_by_severity"].items():
                sev_tot[s] += n

    def badge(sev, n):
        return f'<span class="sev-badge {sev.lower()}">{sev[:4]} {n}</span>'

    def risk_class(r):
        return "risk-high" if r >= 50 else ("risk-medium" if r >= 10 else "risk-low")

    secs = []
    for c in report:
        cards = []
        for p in c["projects"]:
            sb = p["vulnerabilities_by_severity"]
            rows = "".join(
                f'<tr><td>{html.escape(str(v["vulnId"]))}</td>'
                f'<td><span class="sev-badge {str(v["severity"]).lower()}">{html.escape(str(v["severity"]))}</span></td>'
                f'<td>{html.escape(str(v["source"]))}</td>'
                f'<td>{html.escape(str(v["description"]))}</td></tr>'
                for v in p["top_vulnerabilities"]) or '<tr><td colspan="4" style="color:#22c55e">No vulnerabilities 🎉</td></tr>'
            cards.append(f"""
      <div class="project-card">
        <h3>{html.escape(p['name'])} <small style="color:#64748b">{html.escape(str(p['version']))}</small></h3>
        <p class="project-desc">{html.escape(p['description'])}</p>
        <div class="metric-row"><span class="metric-label">Components</span><span class="metric-value">{p['total_components']}</span></div>
        <div class="metric-row"><span class="metric-label">Vulnerabilities</span><span class="metric-value">{p['total_vulnerabilities']}</span></div>
        <div class="metric-row"><span class="metric-label">Risk score</span><span class="metric-value {risk_class(p['risk_score'])}">{p['risk_score']}</span></div>
        <div class="sev-badges">{badge('CRITICAL', sb['CRITICAL'])}{badge('HIGH', sb['HIGH'])}{badge('MEDIUM', sb['MEDIUM'])}{badge('LOW', sb['LOW'])}</div>
        <table class="vuln-table"><tr><th>Vuln</th><th>Severity</th><th>Source</th><th>Description</th></tr>{rows}</table>
      </div>""")
        secs.append(f"""
    <div class="company-section">
      <div class="company-header">
        <span class="company-name">{html.escape(c['company_name'])}</span>
        <!-- <a class="company-badge" href="{html.escape(c['frontend_url'])}" target="_blank">{html.escape(c['frontend_url'])}</a> -->
      </div>
      <div class="project-grid">{''.join(cards)}</div>
    </div>""")

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Combined Dependency-Track Report</title><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',Tahoma,sans-serif; background:#0f172a; color:#e2e8f0; padding:20px; }}
.container {{ max-width:1400px; margin:0 auto; }}
h1 {{ text-align:center; color:#38bdf8; margin-bottom:8px; }}
.subtitle {{ text-align:center; color:#94a3b8; margin-bottom:30px; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:16px; margin-bottom:30px; }}
.summary-card {{ background:#1e293b; border-radius:12px; padding:20px; text-align:center; border:1px solid #334155; }}
.summary-card .value {{ font-size:2.4em; font-weight:700; color:#38bdf8; }}
.summary-card .label {{ color:#94a3b8; margin-top:4px; }}
.company-section {{ background:#1e293b; border-radius:12px; padding:24px; margin-bottom:24px; border:1px solid #334155; }}
.company-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }}
.company-name {{ font-size:1.5em; font-weight:700; color:#f1f5f9; }}
.company-badge {{ background:#334155; padding:6px 14px; border-radius:20px; font-size:0.85em; color:#cbd5e1; text-decoration:none; }}
.project-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(420px,1fr)); gap:16px; }}
.project-card {{ background:#0f172a; border-radius:10px; padding:18px; border:1px solid #334155; }}
.project-card h3 {{ color:#38bdf8; margin-bottom:8px; }}
.project-desc {{ color:#94a3b8; font-size:0.9em; margin-bottom:12px; }}
.metric-row {{ display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #1e293b; }}
.metric-label {{ color:#94a3b8; }} .metric-value {{ font-weight:600; }}
.sev-badges {{ display:flex; gap:8px; flex-wrap:wrap; margin:12px 0; }}
.sev-badge {{ padding:4px 10px; border-radius:12px; font-size:0.78em; font-weight:600; }}
.sev-badge.critical {{ background:rgba(239,68,68,.2); color:#ef4444; }}
.sev-badge.high {{ background:rgba(249,115,22,.2); color:#f97316; }}
.sev-badge.medium {{ background:rgba(234,179,8,.2); color:#eab308; }}
.sev-badge.low {{ background:rgba(34,197,94,.2); color:#22c55e; }}
.sev-badge.unassigned {{ background:rgba(107,114,128,.2); color:#9ca3af; }}
.vuln-table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
.vuln-table th {{ text-align:left; padding:8px; color:#94a3b8; border-bottom:1px solid #334155; font-size:0.8em; }}
.vuln-table td {{ padding:8px; border-bottom:1px solid #1e293b; font-size:0.8em; vertical-align:top; }}
.risk-high {{ color:#ef4444; }} .risk-medium {{ color:#f97316; }} .risk-low {{ color:#22c55e; }}
.footer {{ text-align:center; color:#64748b; margin-top:30px; padding-top:20px; border-top:1px solid #334155; }}
</style></head><body><div class="container">
<h1>Combined Dependency-Track Report</h1>
<p class="subtitle">Multi-Company Vulnerability Monitoring — Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<div class="summary-grid">
  <div class="summary-card"><div class="value">{companies}</div><div class="label">Companies</div></div>
  <div class="summary-card"><div class="value">{projects}</div><div class="label">Projects</div></div>
  <div class="summary-card"><div class="value">{comps}</div><div class="label">Components</div></div>
  <div class="summary-card"><div class="value">{vulns}</div><div class="label">Vulnerabilities</div></div>
  <div class="summary-card"><div class="value" style="color:#ef4444">{sev_tot['CRITICAL']}</div><div class="label">Critical</div></div>
  <div class="summary-card"><div class="value" style="color:#f97316">{sev_tot['HIGH']}</div><div class="label">High</div></div>
</div>
{''.join(secs)}
<div class="footer">Generated from a single Dependency-Track instance (team-based multi-tenancy) · combined_report.py</div>
</div></body></html>"""


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    print("Collecting from Dependency-Track instances...")
    report = collect()

    json_path = os.path.join(REPORT_DIR, "combined_report_latest.json")
    html_path = os.path.join(REPORT_DIR, "combined_report_latest.html")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(report))

    total_comp = sum(p["total_components"] for c in report for p in c["projects"])
    total_vuln = sum(p["total_vulnerabilities"] for c in report for p in c["projects"])
    print(f"\n  Companies: {len(report)}  Projects: {sum(len(c['projects']) for c in report)}"
          f"  Components: {total_comp}  Vulnerabilities: {total_vuln}")
    print(f"  JSON: {json_path}\n  HTML: {html_path}")
    if total_comp == 0:
        print("\n  NOTE: all metrics are 0 — Dependency-Track is probably still analyzing the")
        print("        uploaded SBOMs. Wait 2-3 minutes and re-run this script.")

    if "--serve" in sys.argv:
        import http.server, socketserver
        port = 8090
        for a in sys.argv[sys.argv.index("--serve") + 1:]:
            if a.isdigit():
                port = int(a); break
        os.chdir(REPORT_DIR)
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("0.0.0.0", port), http.server.SimpleHTTPRequestHandler) as httpd:
            print(f"\n  Serving on 0.0.0.0:{port} — open:")
            print(f"      http://<server-ip>:{port}/combined_report_latest.html")
            print("  Ctrl+C to stop.")
            httpd.serve_forever()


if __name__ == "__main__":
    main()
