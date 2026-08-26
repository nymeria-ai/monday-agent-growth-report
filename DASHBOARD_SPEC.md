# monday.com Agent Growth Report — Dashboard Specification

> **Purpose of this document**
> Paste this file into any AI agent to instantly rebuild, debug, or extend the dashboard. It is the single source of truth for how every number is pulled, calculated, and displayed.

---

## 1. What the Dashboard Is

A weekly HTML report tracking the performance of monday.com's **AI Agent search campaigns** across Google Ads. It covers spend, impressions, clicks, signups, paying conversions, Agent Created conversions, and funnel metrics — broken down by campaign and week.

**Live URL:** https://nymeria-ai.github.io/monday-agent-growth-report/  
**Repo:** `nymeria-ai/monday-agent-growth-report` (GitHub Pages, `main` branch)  
**Build output:** `index.html` (single self-contained file, all JS/CSS inline)

---

## 2. Data Sources

### 2.1 Google Ads Accounts

| Account Name | Customer ID | Contents |
|---|---|---|
| Main | `3746504118` | All standard agent campaigns |
| Verticals | `6629846296` | AI Marketing, AI Construction |

Data is pulled via **Funnel Gate** (`funnel_gate.py`) — a local proxy that handles OAuth and Google Ads API (gRPC). Never call the Google Ads REST API directly; it returns 404 (developer token in test mode, gRPC only).

### 2.2 Date Windows

| Window | Variable | Default Range |
|---|---|---|
| Weekly trend | `WEEKLY_START` → `WEEKLY_END` | Last ~10 weeks (e.g. 2026-06-15 → 2026-08-23) |
| Since-launch (funnel table) | `LAUNCH_START` → `LAUNCH_END` | 2026-05-06 → same end date |

Both variables are hardcoded in `agent-report-collect.py`. Update them each refresh cycle.

---

## 3. Campaign Taxonomy

### 3.1 Naming Convention

Google Ads campaign names follow the pattern:
```
{geo}-{lang}-prm-{product}-{type}-{segment}-{device}-{targeting}-aw
```

Examples:
- `us-en-prm-work_mgmt-search-agent_aihr-h-desktop-core-aw`
- `au-en-prm-work_mgmt-search-agent_aimarketing-h-desktop-core-aw`

**Key segment in the name:** the `agent_*` token maps to a campaign group (see §3.2).

### 3.2 Campaign Groups

The `get_camp_key()` function in `agent-report-build.py` maps raw campaign names to canonical keys:

| Key | Display Name | Account | Campaign Name Contains |
|---|---|---|---|
| `work_agent` | Work Agent | Main | `agent_aiwork_builder` or `agent_aiwork_agent` |
| `aicomp` | AI Comp | Main | `agent_aicomp` + comp1 ad groups (see §3.3) |
| `aihr` | AI HR | Main | `agent_aihr` |
| `aiit` | AI IT | Main | `agent_aiit` |
| `ailegal` | AI Legal | Main | `agent_ailegal` or `agent_ailegal_contract` |
| `aifinance` | AI Finance | Main | `agent_aifinance` |
| `ainote_taker` | AI Note Taker | Main | `agent_ainote_taker` |
| `aireal_estate` | AI Real Estate | Main | `agent_aireal_estate` |
| `aiwork_process` | AI Work Process | Main | `agent_aiwork_process` |
| `aipmo` | AI PMO | Main | `agent_aipmo` or `aipmo` |
| `aimarketing` | AI Marketing | Verticals | `agent_aimarketing` |
| `aiconstruction` | AI Construction | Verticals | `agent_aiconstruction` |

**Filter applied to all campaign queries:**
```sql
WHERE campaign.name LIKE '%agent%'
  AND campaign.name NOT LIKE '%crm%'
```

### 3.3 AI Comp Special Case

The `aicomp` group **merges two sources**:
1. Standard `agent_aicomp` campaign (pulled with all others)
2. Agent-themed ad groups within `us-en-prm-workos-work_mgmt-comp1-h-search-desktop-exp-aw` — ad groups filtered by `ad_group.name LIKE '%agent%'`, data pulled from **2026-06-22 onwards** (campaign restructure date)

This merge happens in the build script by summing both sources into `aicomp`.

### 3.4 Display Order

Campaigns appear in this order in the Funnel & Paying Analysis table (sorted by spend) and in per-campaign blocks (fixed order):

```
work_agent → aicomp → aihr → aiit → ailegal → aifinance →
ainote_taker → aireal_estate → aiwork_process → aipmo →
aimarketing → aiconstruction
```

Per-campaign blocks are grouped under account dividers: **Main (3746504118)** then **Verticals (6629846296)**.

---

## 4. Metrics — How Each Is Pulled and Calculated

### 4.1 Google Ads GAQL Fields

| Metric | GAQL Field | Notes |
|---|---|---|
| Spend | `metrics.cost_micros` | Divide by 1,000,000 for dollars |
| Impressions | `metrics.impressions` | Raw integer |
| Clicks | `metrics.clicks` | Raw integer |
| All conversions | `metrics.all_conversions_by_conversion_date` | Segmented by `conversion_action_name` |

All conversion data uses **`all_conversions_by_conversion_date`** (attribution by conversion date, not click date). This is different from `conversions` and `all_conversions`.

### 4.2 Conversion Actions

| Conversion Action Name | Maps To | Field in Data |
|---|---|---|
| `Hard Signup (MCC)` | Hard Signups | `signups` |
| `Paying (MCC)` | Payers | `paying` |
| `Agent Created (MCC)` | Agent Created | `agent_created` |
| `Hard signup Work goal (MCC)` | Work Signups (%Work) | `work_su` |

### 4.3 Derived Metrics (all calculated in `agent-report-build.py`)

| Metric | Formula | Description |
|---|---|---|
| CTR | clicks / impressions | Click-through rate |
| CR | signups / clicks | Click-to-hard-signup conversion rate |
| CPS | spend / signups | Cost per hard signup |
| %Work | work_su / signups | Share of signups who signed up for Work product |
| CVR Paying | paying / signups | Signup-to-paying conversion rate |
| CAC | spend / paying | Cost to acquire a paying customer |
| CPAC | spend / agent_created | Cost per agent created |
| AC Rate | agent_created / signups | Share of signups who created an agent |

### 4.4 Color Thresholds (Funnel & Paying Analysis table)

| Metric | Green (good) | Red (bad) |
|---|---|---|
| CTR | > 4% | < 2% |
| CR | > 10% | < 5% |
| %Work | > 55% | < 35% |
| CVR Paying | > 0.5% | < 0.2% |
| AC Rate | > 8% | < 3% |

---

## 5. Dashboard Sections

### 5.1 Header KPI Bar
- **Week-over-week KPIs** (4 cards): Total Spend, Impressions, Hard Signups, Paying — each showing the latest week's value and a Δ% vs the prior week.
- **Date range label:** "May 6 – [last data date], YYYY · All accounts"

### 5.2 Overall Weekly Trend Table
Columns: `Week | Spend | Δ | Imp | Δ | Signups | Δ | CPS | Payers | CAC | Agent Created | Δ | CPAC`

One row per week. Only weeks with at least one impression or dollar of spend are shown. Δ = week-over-week change.

### 5.3 Funnel Visualizer Bar
A horizontal funnel showing the overall (since-launch) conversion chain:
`Impressions → CTR → CR to Signup → %Work → CVR Paying → Agent Created`

Interactive: date range slider filters all values in this bar AND in the weekly charts.

### 5.4 Funnel & Paying Analysis Table
Columns: `Campaign | Spend | Imp | CTR | CR | Signups | CPS | Work SU | %Work | Payers | CAC | CVR Pay | AC | AC Rate | CPAC`

One row per campaign. Data is **since-launch** (LAUNCH_START → LAUNCH_END). Rows sorted by spend descending. Color-coded cells (see §4.4). Total row at bottom.

### 5.5 Observation Boxes
Auto-generated text observations below the funnel table:
1. **CR** — lowest and highest CR campaigns
2. **%Work** — highest and lowest %Work campaigns (min 10 signups)
3. **CVR Paying** — top converters to paying
4. **AC Rate** — highest agent-creation rates

### 5.6 Per-Campaign Detail Blocks
One collapsible block per campaign, ordered by account then CAMP_ORDER. Each block contains:

**KPI Cards (last week vs prior week):** Spend Δ, Impressions Δ, Hard Signups Δ, Payers (launch total + "X this week")

**Weekly Trend Table:** Same columns as §5.2, but only this campaign's data. Skips zero-data weeks.

**Ad Group Breakdown Table:** Columns: `Ad Group | Spend | Imp | Clicks | Signups | Payers | AC` — launch-period totals, sorted by spend. Only shows enabled ad groups (status = ENABLED).

**Badges:**
- `restructured Jun 22` — AI Comp (comp1 merge date)
- `new` — AI Finance, AI Note Taker, AI Real Estate, AI Work Process, AI Construction

---

## 6. Date Range Filter (JavaScript)

An interactive date range slider at the top of the report lets users filter to any sub-range. It updates:
- The funnel bar values
- The weekly trend table (shows only weeks within range)
- The per-campaign KPI cards and trend tables

**Data embedded in JS:**
- `CAMPAIGN_WEEKLY` — per-campaign, per-week: spend, imp, signups, payers, ac
- `AG_WEEKLY` — per-campaign, per-ad-group, per-week: same fields

The JS is generated at build time and inlined into `index.html`. No external API calls at render time — the report is fully static.

---

## 7. Build & Refresh Pipeline

### 7.1 Scripts

| Script | Path | Role |
|---|---|---|
| Collect | `ff-sem-deploy/scripts/agent-report-collect.py` | Queries Google Ads via Funnel Gate, outputs JSON |
| Build | `ff-sem-deploy/scripts/agent-report-build.py` | Reads JSON, renders `index.html` |

### 7.2 Run Order

```bash
# Step 1: Collect fresh data
python3 agent-report-collect.py > /tmp/agent-report-data.json

# Step 2: Build HTML
python3 agent-report-build.py > /tmp/monday-agent-growth-report/index.html

# Step 3: Commit and push
cd /tmp/monday-agent-growth-report
git add index.html
git commit -m "Weekly report W{week} ({date range})"
git push origin main
# GitHub Pages auto-deploys in ~1 minute
```

### 7.3 Refresh Cadence

**Manual — triggered on demand** (no cron job). The report is typically refreshed weekly by the SEM team. There is no automated schedule; someone must run the collect + build scripts and push to GitHub.

### 7.4 Authentication

- **Funnel Gate:** running locally on `http://localhost:9400`
- **Google Ads token:** stored encrypted in Funnel Gate vault (`ygritte` agent, `google_ads` platform)
- **Token TTL:** Google Ads OAuth refresh tokens expire after ~7 days. If `agent-report-collect.py` returns 401 errors, run the Google Ads OAuth renewal flow (`skills/google-ads-oauth-renew/scripts/renew_google_ads_oauth.js`)
- **GitHub push:** PAT at `/opt/ocana/.openclaw/.secrets/github_pat.enc` (decrypt with machine-id)

---

## 8. How to Add a New Campaign

1. **`agent-report-build.py`** — `get_camp_key()`: add an `elif 'agent_NEWKEY' in name` clause
2. **`agent-report-build.py`** — `CAMP_DISPLAY`: add `'newkey': 'Display Name'`
3. **`agent-report-build.py`** — `CAMP_ACCOUNT`: add `'newkey': 'Main (3746504118)'` (or Verticals)
4. **`agent-report-build.py`** — `CAMP_ORDER`: insert at the desired position
5. Re-collect data and rebuild (`WEEKLY_START`/`LAUNCH_START` must predate the campaign launch)
6. Update this document: add a row to §3.2 and note the launch date in §5.6 badges if needed

---

## 9. How to Add a New Metric

1. Ensure the GAQL query in `agent-report-collect.py` includes the new field
2. Parse it in the relevant `camp_weekly`, `camp_conv_weekly`, or `camp_launch` loops in `agent-report-build.py`
3. Add the derived formula to §4.3 of this document
4. Add a column header in the HTML template string and a `{value}` in `funnel_table_rows` / `build_weekly_trend_row()`
5. Add color thresholds if applicable (§4.4)

---

## 10. Changelog

| Date | Change | Who |
|---|---|---|
| 2026-08-26 | Added AI PMO campaign (`agent_aipmo`) | Tal Herman / Ygritte |
| 2026-08-26 | CPAC column added to Funnel & Paying Analysis table | Tal Herman / Ygritte |
| 2026-08-26 | This spec document created and embedded in report | Ygritte |
| 2026-08-12 | W33 data refresh (Aug 4–10) | Ygritte |
| 2026-07-27 | AI Construction added (Verticals account) | SEM team |
| 2026-07-13 | AI Finance, AI Note Taker, AI Real Estate, AI Work Process added | SEM team |
| 2026-06-22 | AI Comp restructured — comp1 agent ad groups merged in | SEM team |
| 2026-05-06 | Dashboard launched | SEM team |
