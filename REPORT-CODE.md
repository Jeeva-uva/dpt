# `report.html`, explained piece by piece

This is a walkthrough of every block of code in `report.html`, what it does, and how
the pieces fit into the overall flow. The whole file is one static HTML+JS document
of about 200 lines — no build step, no backend, just the browser talking directly to
the Dependency-Track REST API.

---

## Big picture

When the page loads:

1. The browser downloads Tailwind from a CDN (one `<script src>` tag).
2. The JavaScript runs `refresh()` once automatically.
3. `refresh()` calls the DT API a handful of times: one call for the team list, one
   call per team to list its ACL-mapped projects, then for each project two more calls
   (metrics + findings).
4. The results get rolled into portfolio totals and rendered as 6 summary cards plus
   one section per team. Clicking the Refresh button re-runs that same flow.

Two hardcoded constants point at the DT instance — `API_URL` and `API_KEY` — and that
is the entirety of the configuration.

---

## The HTML shell

### Head

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Combined Dependency-Track Report</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',Tahoma,sans-serif}</style>
</head>
```

Standard HTML head plus two things that matter:

- **`<script src="https://cdn.tailwindcss.com">`** is the Tailwind Play CDN. It scans
  the DOM at runtime, sees the utility classes we use (`bg-slate-800`, `text-sky-400`,
  etc.), and generates the matching CSS on the fly. That's why we don't ship any
  stylesheet of our own.
- **`<style>`** sets the dark page background (`#0f172a`), the light text colour, and
  the page font in a single line. Everything else — cards, badges, tables — is styled
  by Tailwind utility classes directly on the elements.

### Body

```html
<body class="p-5">
<div class="max-w-7xl mx-auto">

  <h1 class="text-3xl font-bold text-sky-400 text-center mb-1">Combined Dependency-Track Report</h1>
  <p class="text-slate-400 text-center mb-4">Multi-Company Vulnerability Monitoring</p>

  <div class="text-center mb-6">
    <button id="refresh"
      class="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-semibold px-6 py-2 rounded">
      ↻ Refresh
    </button>
  </div>

  <div id="status" class="text-slate-400 text-center mb-4 min-h-[1.25rem]"></div>

  <div id="summary" class="grid gap-4 mb-6 hidden"
       style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr))"></div>

  <div id="companies"></div>

  <div id="footer" class="text-center text-slate-500 mt-8 pt-5 border-t border-slate-700 hidden">
    Generated <span id="ts"></span>
  </div>
</div>
```

The body is empty containers that the script will fill in:

- A centred title and subtitle (sky-blue + muted slate).
- A `#refresh` button — the only interactive element. `disabled:opacity-50` dims it
  while a fetch is in flight.
- A `#status` line that displays *"Fetching teams…"*, *"Loading Acme Corp…"* and any
  error messages.
- An empty `#summary` grid — populated with the six totals cards. The inline style
  `grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))` lets the cards reflow
  to the window width.
- `#companies` — the script appends one section per team here.
- A `#footer` with a `#ts` span the script fills with the generated timestamp.

`hidden` is on `#summary` and `#footer` so nothing flashes empty before the first
fetch completes.

---

## The JavaScript

### Hardcoded configuration

```js
const API_URL = "http://145.100.105.193:8088";
const API_KEY = "odt_lLyxR0C8_l7kaZnEobEisCo0rYSrF4uRfwVgtCspX";
```

Two constants and only two. `API_URL` must be a URL the **browser** can reach (not
just the DT host — `localhost` only works if you're browsing from the DT host
itself). `API_KEY` is sent as `X-Api-Key` on every request; it needs the DT
permissions `VIEW_PORTFOLIO`, `VIEW_VULNERABILITY`, and `VIEW_BADGES`. Both values
live in the file in plain text, so anyone who can read the file gets the key.

### Tiny shortcuts

```js
const $ = id => document.getElementById(id);
const SEV = { CRITICAL:0, HIGH:1, MEDIUM:2, LOW:3, INFO:4, UNASSIGNED:5 };
const TOP_N = 5;
```

`$` is just a shorter `getElementById`. `SEV` maps a severity string to a numeric
rank that's used to sort findings so the worst come first. `TOP_N` caps the number
of vulnerabilities shown per project to keep cards compact.

### HTML escaper

```js
const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
```

Every value coming from Dependency-Track goes through `esc()` before being injected
into the DOM. Vulnerability descriptions in particular can contain `<` or `&` — left
unescaped, they would either break the page layout or, in the worst case, inject
markup. `String(s ?? '')` first guards against `null`/`undefined`.

### Severity and risk colour helpers

```js
const sevCls = s => ({
  CRITICAL:'bg-red-500/20 text-red-400',
  HIGH:'bg-orange-500/20 text-orange-400',
  MEDIUM:'bg-yellow-500/20 text-yellow-400',
  LOW:'bg-green-500/20 text-green-400',
  UNASSIGNED:'bg-slate-500/20 text-slate-400'
}[s] || 'bg-slate-500/20 text-slate-400');

const riskCls = r => r >= 50 ? 'text-red-400' : r >= 10 ? 'text-orange-400' : 'text-green-400';
```

`sevCls(severity)` returns the Tailwind class pair for that severity — a translucent
background (`/20` = 20% opacity) plus a matching text colour. Unknown values fall
back to the slate (grey) pair.

`riskCls(score)` turns a numeric risk into a colour: red at 50+, orange from 10, green
otherwise. The thresholds are arbitrary but match the dashboard's visual intent —
high risk pops red on the page.

### The HTTP helper

```js
async function get(url) {
  try {
    const r = await fetch(url, { headers: { 'X-Api-Key': API_KEY } });
    return r.ok ? r.json() : null;
  } catch { return null; }
}
```

A thin wrapper around `fetch` that:

- Adds the `X-Api-Key` header so every call is authenticated.
- Returns parsed JSON on a 2xx response.
- Returns `null` on any failure — non-2xx status, network error, CORS block, JSON
  parse error.

Returning `null` rather than throwing means the calling code can do
`const x = await get(...) || []` and never crash. One failed metric never breaks the
whole page.

### Template: the summary card

```js
const sumCard = (label, value, color = 'text-sky-400') => `
  <div class="bg-slate-800 border border-slate-700 rounded-xl p-5 text-center">
    <div class="text-4xl font-bold ${color}">${value}</div>
    <div class="text-slate-400 mt-1">${label}</div>
  </div>`;
```

Returns the HTML string for one summary card — a large coloured number above a muted
label. `color` defaults to sky-blue; the Critical and High cards override it to red
and orange.

### Template: the project card

```js
const projectCard = p => {
  const sb = p.severities;
  const badges = ['CRITICAL','HIGH','MEDIUM','LOW'].map(s =>
    `<span class="px-2.5 py-1 rounded-full text-xs font-semibold ${sevCls(s)}">${s.slice(0,4)} ${sb[s]||0}</span>`
  ).join('');
  const rows = (p.top || []).map(v => `
    <tr class="border-b border-slate-800">
      <td class="p-2 text-xs">${esc(v.vulnId)}</td>
      <td class="p-2 text-xs"><span class="px-2 py-0.5 rounded-full ${sevCls(v.severity)}">${esc(v.severity)}</span></td>
      <td class="p-2 text-xs">${esc(v.source)}</td>
      <td class="p-2 text-xs text-slate-300">${esc(v.description)}</td>
    </tr>`).join('')
    || `<tr><td colspan="4" class="p-3 text-center text-green-400 text-sm">No vulnerabilities 🎉</td></tr>`;
  return `
    <div class="bg-slate-900 border border-slate-700 rounded-lg p-4">
      <h3 class="text-sky-400 font-semibold mb-1">${esc(p.name)}
        <span class="text-slate-500 text-sm font-normal">${esc(p.version || '')}</span></h3>
      <p class="text-slate-400 text-sm mb-3">${esc(p.description)}</p>
      <div class="flex justify-between border-b border-slate-800 py-1.5"><span class="text-slate-400">Components</span><span class="font-semibold">${p.components}</span></div>
      <div class="flex justify-between border-b border-slate-800 py-1.5"><span class="text-slate-400">Vulnerabilities</span><span class="font-semibold">${p.vulnerabilities}</span></div>
      <div class="flex justify-between border-b border-slate-800 py-1.5"><span class="text-slate-400">Risk score</span><span class="font-semibold ${riskCls(p.risk)}">${p.risk}</span></div>
      <div class="flex flex-wrap gap-2 my-3">${badges}</div>
      <table class="w-full border-collapse">
        <thead><tr class="border-b border-slate-700">
          <th class="text-left text-xs text-slate-400 p-2">Vuln</th>
          <th class="text-left text-xs text-slate-400 p-2">Severity</th>
          <th class="text-left text-xs text-slate-400 p-2">Source</th>
          <th class="text-left text-xs text-slate-400 p-2">Description</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
};
```

The biggest template, built in three parts:

- **`badges`** is the row of CRIT/HIGH/MEDI/LOW pills. For each of the four
  severities it generates a `<span>` styled with that severity's `sevCls()` colours,
  showing the first 4 letters and the count.
- **`rows`** is the body of the findings table — one row per top vulnerability, with
  every value passed through `esc()`. If the project has no findings the row falls
  back to a green *"No vulnerabilities 🎉"* line.
- **The card itself** is then assembled: project name + version, description, three
  metric rows (Components, Vulnerabilities, Risk score with `riskCls()` colour), the
  badge row, and the findings table.

The metric rows use Flexbox (`flex justify-between`) to push the label left and the
value right, with a thin bottom border separating them — that's the horizontal "list"
look in the dashboard.

### Template: the company section

```js
const companySection = c => `
  <div class="bg-slate-800 border border-slate-700 rounded-xl p-6 mb-6">
    <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
      <span class="text-2xl font-bold text-slate-100">${esc(c.name)}</span>
      <span class="bg-slate-700 px-3.5 py-1.5 rounded-full text-sm text-slate-300">${c.projects.length} project${c.projects.length===1?'':'s'}</span>
    </div>
    <div class="grid gap-4" style="grid-template-columns:repeat(auto-fit,minmax(420px,1fr))">
      ${c.projects.map(projectCard).join('')}
    </div>
  </div>`;
```

Wraps that company's project cards in a panel. The header is a flex row with the team
name on the left and a count badge (`"2 projects"`) on the right. The cards
themselves sit in a CSS grid that wraps to fit the window — each card wants at least
420px; if there's only room for one column, they stack.

### The main flow — `refresh()`

```js
async function refresh() {
  $('refresh').disabled = true;
  $('summary').classList.add('hidden');
  $('footer').classList.add('hidden');
  $('companies').innerHTML = '';
  $('status').textContent = 'Fetching teams...';
```

Sets up a clean slate: disable the button (so impatient double-clicks don't queue),
hide the previous summary and footer, wipe the company sections, and put a status
message up so you can tell something's happening.

```js
  const teams = await get(`${API_URL}/api/v1/team`);
  if (!teams) {
    $('status').textContent = `Could not reach ${API_URL} - check the DT URL, the API key, and that CORS is enabled.`;
    $('refresh').disabled = false; return;
  }
```

The first API call. If `get()` returned `null`, the most likely culprit is one of
three things — wrong URL, wrong key, or CORS not enabled on the apiserver — and the
status line says so explicitly. The button is re-enabled so you can fix the
problem and retry.

```js
  const companies = [];
  for (const t of teams) {
    $('status').textContent = `Loading ${t.name}...`;
    const projects = await get(`${API_URL}/api/v1/acl/team/${t.uuid}?pageSize=500&pageNumber=1`) || [];
    if (!projects.length) continue;
```

For each team, fetch the projects assigned to it via ACL (`/api/v1/acl/team/{uuid}`).
`pageSize=500` is a one-shot upper bound — we don't paginate beyond 500 projects per
team. If a team has no projects (e.g. the default *Administrators* team), `continue`
skips it. That's why empty teams never appear as empty sections on the page.

```js
    const projList = [];
    for (const p of projects) {
      const m = await get(`${API_URL}/api/v1/metrics/project/${p.uuid}/current`) || {};
      const findings = await get(`${API_URL}/api/v1/finding/project/${p.uuid}`) || [];
      findings.sort((a, b) =>
        (SEV[(a.vulnerability || {}).severity || 'UNASSIGNED'] ?? 9) -
        (SEV[(b.vulnerability || {}).severity || 'UNASSIGNED'] ?? 9));
```

For each project, two calls in series:

- **Current metrics** — the latest snapshot DT computed (component count,
  vulnerabilities by severity, inheritedRiskScore).
- **Findings** — the individual vulnerabilities matched to this project's components.

The sort uses the `SEV` rank: criticals first, then high, etc. The `?? 9` handles
unknown severities by sending them to the end.

```js
      projList.push({
        name: p.name, version: p.version, description: p.description || '',
        components: m.components || 0,
        vulnerabilities: m.vulnerabilities || 0,
        risk: m.inheritedRiskScore || 0,
        severities: {
          CRITICAL: m.critical || 0, HIGH: m.high || 0, MEDIUM: m.medium || 0,
          LOW: m.low || 0, UNASSIGNED: m.unassigned || 0
        },
        top: findings.slice(0, TOP_N).map(f => {
          const v = f.vulnerability || {};
          return { vulnId: v.vulnId, severity: v.severity, source: v.source,
                   description: (v.description || '').slice(0, 220) };
        })
      });
    }
    companies.push({ name: t.name, projects: projList });
  }
```

Two pieces of important data shaping:

- A flat project record is built with exactly the fields `projectCard()` consumes —
  this decouples the template from DT's raw response shape.
- `findings.slice(0, TOP_N)` keeps only the top 5, and each finding's description is
  truncated to 220 characters so it fits cleanly in the table cell.

The team gets pushed as `{name, projects}`. If `projList` ended up empty (shouldn't
normally happen, but possible if every project's metric call failed), the company
still gets pushed; the team header just shows "0 projects" and the grid is empty.

```js
  if (!companies.length) {
    $('status').textContent = 'No teams with projects found.'; $('refresh').disabled = false; return;
  }
```

Fallback message if every team was skipped. Means DT is reachable but nothing is
configured.

```js
  const tot = companies.reduce((a, c) => {
    a.projects += c.projects.length;
    for (const p of c.projects) {
      a.comps += p.components; a.vulns += p.vulnerabilities;
      a.crit += p.severities.CRITICAL; a.high += p.severities.HIGH;
    }
    return a;
  }, { projects: 0, comps: 0, vulns: 0, crit: 0, high: 0 });
```

One pass over all companies and projects to compute the six portfolio totals that go
into the summary cards.

```js
  $('summary').innerHTML = [
    sumCard('Companies', companies.length),
    sumCard('Projects', tot.projects),
    sumCard('Components', tot.comps),
    sumCard('Vulnerabilities', tot.vulns),
    sumCard('Critical', tot.crit, 'text-red-500'),
    sumCard('High', tot.high, 'text-orange-500')
  ].join('');
  $('summary').classList.remove('hidden');
  $('companies').innerHTML = companies.map(companySection).join('');
  $('ts').textContent = new Date().toLocaleString();
  $('footer').classList.remove('hidden');
  $('status').textContent = '';
  $('refresh').disabled = false;
}
```

The render step:

- Build the six summary cards as one HTML string and drop it into `#summary`, then
  un-hide it.
- Map each company through `companySection()` and drop the joined HTML into
  `#companies`.
- Stamp the footer with the current local time and un-hide it.
- Clear the status line and re-enable the Refresh button.

### Wire-up

```js
$('refresh').addEventListener('click', refresh);
refresh();   // auto-fetch on first load
```

Two lines, big impact. The button is wired to `refresh()` — that's the *Refresh*
behaviour. The bare `refresh()` call at the end means the page **fetches on load**;
you don't have to click anything to see the first dashboard.

---

## How a single click maps to what you see

For three teams with two projects each, one click runs **16 API calls**:

```
GET /api/v1/team                                                              1
GET /api/v1/acl/team/{acme-uuid}?pageSize=500&pageNumber=1                    1
GET /api/v1/acl/team/{beta-uuid}?pageSize=500&pageNumber=1                    1
GET /api/v1/acl/team/{gamma-uuid}?pageSize=500&pageNumber=1                   1
GET /api/v1/metrics/project/{uuid}/current   (x6 projects)                    6
GET /api/v1/finding/project/{uuid}           (x6 projects)                    6
                                                                            ---
                                                                             16
```

All sequential. On a fast network that's ~3-5 seconds total; on a slow one, longer —
which is why the status line is updated at each major step.

The returned data lands in this rough shape before rendering:

```js
[
  { name: "Acme Corp", projects: [
      { name, version, description,
        components, vulnerabilities, risk,
        severities: { CRITICAL, HIGH, MEDIUM, LOW, UNASSIGNED },
        top: [ { vulnId, severity, source, description }, ... up to 5 ] },
      ...
  ]},
  ...
]
```

The render then loops over that array, calling `companySection` for each entry,
which in turn calls `projectCard` for each project, which assembles the badges and
table rows. All of it is plain string concatenation — there's no virtual DOM, no
framework, just `innerHTML` and template literals.

---

## What can go wrong, and what you'll see

| Symptom on the page | Most likely cause |
|---|---|
| *"Could not reach &lt;url&gt; — check the DT URL, the API key, and that CORS is enabled."* | CORS is off on the apiserver, the URL is wrong, the API key is wrong or expired, or the DT host is unreachable from the browser. |
| *"No teams with projects found."* | The page reached DT successfully, but every team has zero ACL-mapped projects. Add projects to a team's ACL. |
| Page renders but every card shows **0 vulnerabilities** | DT is running and analysed the SBOMs, but no vulnerabilities matched. Almost always means OSV / GitHub Advisories aren't enabled — see *Gotchas* in `REPORT-SETUP.md`. |
| Components / risk all zero on one project | DT hasn't finished analysing yet. Click Refresh again in a minute, or re-upload the BOM. |
| Some teams missing entirely | Those teams have no projects in their ACL (intentional — keeps the page tidy). |

---

## Why it's structured this way

A few deliberate choices worth calling out:

- **One file, no build step.** Tailwind via CDN means no `npm`, no `webpack`, no
  `package.json`. Anyone can open `report.html`, change the two constants, and use it.
- **Plain `fetch` and `innerHTML`.** No framework — easier to read, audit, and
  modify. The trade-off (manual escaping) is handled by `esc()`.
- **Templates return strings, then we use `innerHTML`.** This is fine because every
  user-controlled value goes through `esc()`. It's also dramatically simpler than
  building DOM nodes one at a time.
- **Errors are silent (return `null`).** A single broken project should not break the
  whole page; the rest of the dashboard keeps rendering with what it has.
- **The button is the refresh.** No polling, no auto-refresh interval. You decide
  when fresh data matters — which avoids hammering the DT API.
