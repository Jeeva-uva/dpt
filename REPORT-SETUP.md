# Using `report.html` against your own Dependency-Track instance

The page is a single static file. It calls Dependency-Track's REST API directly from
the browser, lists every team you've configured, fetches that team's ACL-assigned
projects, and renders a combined dashboard. To make it work against any DT instance
(including one you set up manually via the UI), three things have to be in place,
then you change two lines in the HTML.

---

## 1. Set up inside Dependency-Track (via the UI)

The page reads three things via the API: **teams**, **projects mapped to each team via
ACL**, and **metrics + findings per project**. So for every "company" you want to see
as a section:

1. **Create a team.** *Administration → Access Management → Teams → Create Team.* Name
   it the way the company should appear in the report (e.g. `Acme Corp`).
2. **Create the projects** that belong to that company. *Projects → Create Project*,
   then upload an SBOM for each.
3. **Assign each project to its team via ACL.** Open the project → *Permissions* tab →
   add the team. (Equivalent API: `PUT /api/v1/acl/mapping` with body
   `{"team": "<team-uuid>", "project": "<project-uuid>"}`.) The report skips teams with
   no ACL'd projects, so default teams like *Administrators* never show as empty.
4. **Mint a read-only API key.** Use the built-in *Automation* team or make a fresh
   one. Grant it `VIEW_PORTFOLIO`, `VIEW_VULNERABILITY`, and `VIEW_BADGES`. Click
   *Generate API Key* and copy the value (looks like `odt_xxxxxxxxxxxxxxxxxxxx`).

---

## 2. Enable CORS on the apiserver

Without CORS, the browser silently blocks every call from the page. Add these
environment variables to the **apiserver container** and restart it:

```yaml
ALPINE_CORS_ENABLED: "true"
ALPINE_CORS_ALLOW_ORIGIN: "*"
ALPINE_CORS_ALLOW_METHODS: "GET, POST, PUT, DELETE, OPTIONS"
ALPINE_CORS_ALLOW_HEADERS: "Origin, Content-Type, Authorization, X-Requested-With, X-Api-Key, X-Total-Count, *"
ALPINE_CORS_EXPOSE_HEADERS: "Origin, Content-Type, Authorization, X-Requested-With, X-Api-Key, X-Total-Count"
```

Make sure the apiserver's port is reachable from wherever the browser will be
(firewall, cloud security group). The port you put in `API_URL` (next step) must be
open to the browser, not just to the DT host.

---

## 3. Edit two lines in `report.html`

Open the file in any editor and change the two constants near the top of the
`<script>` block:

```js
const API_URL = "http://your-dt-server:port";      // exact apiserver URL the browser reaches
const API_KEY = "odt_xxxxxxxxxxxxxxxxxxxxxxxxxx";  // the key from step 1.4
```

If either is wrong (or CORS is off), the page shows:
*"Could not reach &lt;url&gt; — check the DT URL, the API key, and that CORS is
enabled."*

---

## 4. Open the page

Three common ways — pick whichever fits where the file lives:

- **Just open the file.** Double-click `report.html`, or paste
  `file:///path/to/report.html` into the browser. Works because
  `Access-Control-Allow-Origin: *` accepts the `null` origin browsers use for
  `file://`.
- **Serve it next to DT.** On the DT host:
  ```bash
  cd ~/where/report-is && python3 -m http.server 8090
  ```
  Then from your laptop open `http://<dt-server>:8090/report.html`.
- **Host it anywhere else.** GitHub Pages, an internal static host, your laptop —
  the HTML doesn't have to live on the DT host at all. It just makes API calls to
  whatever `API_URL` points at.

The page auto-fetches on load. Click **↻ Refresh** any time to refetch fresh data
without reloading the page.

---

## What you'll see

- Six summary cards across the top: Companies / Projects / Components / Vulnerabilities
  / Critical / High.
- One section per team, with a card per project showing component count, total
  vulnerabilities, risk score (coloured), CRIT/HIGH/MEDI/LOW badges, and a small table
  of the top 5 findings.
- A "Generated &lt;timestamp&gt;" footer.

The dashboard styling is Tailwind via CDN — no build step, no dependencies. The whole
file is ~200 lines of HTML+JS.

---

## Gotchas worth flagging

- **PURL vs CPE matching.** If your SBOMs are CycloneDX with PURLs (typical Syft
  output: `pkg:npm/...`, `pkg:pypi/...`, `pkg:maven/...`), matches come from **OSV** and
  **GitHub Advisories** — *not* NVD, which uses CPE. If components show but
  Vulnerabilities stay at zero, this is almost always the reason.
- **Enabling OSV.** In *Configuration → Analyzers → OSV*, enable it and list the
  ecosystems you actually use. The config value is **semicolon-separated**, not
  comma — DT splits on `;`. Use e.g.
  `Maven;npm;PyPI;Go;NuGet;RubyGems`. Commas will be treated as one literal
  ecosystem name and the mirror will 404.
- **GitHub Advisories.** Needs a personal access token (`Configuration → Analyzers →
  GitHub Advisories`). Without one it stays effectively disabled.
- **Re-triggering analysis after enabling a new source.** DT only matches against
  vulnerabilities it had when the BOM was last processed. After enabling a new
  source and letting it mirror, re-upload the BOMs (or click *Reanalyze* on each
  project in the UI) to pick up the new matches.
- **API key in plain text.** Anyone who can read the HTML file gets the key. Use a
  read-only key with only the permissions in step 1.4 — never a key with
  `BOM_UPLOAD`, `PROJECT_CREATION_UPLOAD`, `ACCESS_MANAGEMENT`, etc.
- **`localhost` only works when you're browsing from the DT host itself.** From a
  laptop, use the server's real hostname or IP in `API_URL`.
- **Empty teams are skipped.** A team with no ACL'd projects produces no card and no
  section — so the default *Administrators* team won't show up, you don't need to
  delete it.

---

## Verifying the setup quickly (no browser)

Sanity-check that DT is answering the three calls the page makes, using your URL and
key:

```bash
URL=http://your-dt-server:port
KEY=odt_xxxxxxxxxxxxxxxxxxxxxxxxxx

# 1. teams
curl -s -H "X-Api-Key: $KEY" "$URL/api/v1/team" | python3 -m json.tool | head

# 2. one team's ACL-assigned projects (paste a uuid from the first call)
curl -s -H "X-Api-Key: $KEY" "$URL/api/v1/acl/team/<team-uuid>?pageSize=500"

# 3. one project's current metrics (paste a uuid from the second call)
curl -s -H "X-Api-Key: $KEY" "$URL/api/v1/metrics/project/<project-uuid>/current"
```

If all three return JSON (not 401/403/CORS-blocked HTML), the page will work.
