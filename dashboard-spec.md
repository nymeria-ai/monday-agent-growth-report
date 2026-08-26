# Agent Weekly Growth Report — Dashboard Specification

> **Purpose:** This document is the single source of truth for rebuilding, understanding, or extending the Agent Growth Report dashboard. Paste it to an AI agent and it can fully reconstruct the dashboard or answer any question about how it works.

> **Last updated:** 2026-08-26

---

## 1. Overview

A static HTML dashboard (GitHub Pages) tracking weekly performance of monday.com's **AI agent campaigns** across Google Ads Search. Covers all agent verticals from launch (June 2026 onward).

- **URL:** `https://nymeria-ai.github.io/monday-agent-growth-report/`
- **Repo:** `nymeria-ai/monday-agent-growth-report` (GitHub, `main` branch)
- **Stack:** Single `index.html` file with inline CSS + vanilla JS. No frameworks, no build step.
- **Data:** Embedded as JS objects (`CAMPAIGN_WEEKLY`, `AG_WEEKLY`) inside `<script>` tags. No external API calls at runtime.
- **Refresh script:** `refresh.py` (Python 3) pulls fresh data and updates `index.html`.

---

## 2. Data Source & API Access

### Google Ads Accounts

All data is pulled from **5 Google Ads accounts** under the monday.com MCC (`764-577-9471`):

| Account ID | Name | Contains |
|---|---|---|
| `3746504118` | Main | Work Agent, AI Comp, AI HR, AI IT, AI Legal, AI Finance, AI Note Taker, AI Real Estate, AI Work Process |
| `6629846296` | Verticals | AI Marketing, AI Construction |
| `9194503735` | Verticals2 | (overflow verticals) |
| `9441310809` | Locals | (localized campaigns) |
| `6073520942` | Brand | (brand campaigns) |

### API Access

- All queries go through **Funnel Gate** (`http://localhost:9400/execute`) — a local proxy that handles OAuth tokens and audit logging.
- API action: `gaql_query` on platform `google_ads`.
- **Never call Google Ads API directly.** Funnel Gate manages auth tokens and audit trail.
- Channel type filter: `campaign.advertising_channel_type = 'SEARCH'` (Search only, no Display/Video).

### Data Range

- **Start date:** `2026-06-01` (hardcoded in `refresh.py` as `START_DATE`)
- **End date:** Yesterday (dynamically computed at refresh time)

---

## 3. Campaign Identification & Naming

### Campaign Name → Agent Mapping

Campaigns are identified by parsing their **campaign name** using a hyphen-delimited naming convention. The `extract_agent()` function handles this:

#### Format 1: PRM campaigns (most common)
```
{geo}-{lang}-prm-{product}-{channel}-{cluster}-{match}-{device}-{theme}-{network}
```
Example: `us-en-prm-work_mgmt-search-agent_aihr-h-desktop-core-aw`
- Position `[5]` (0-indexed) = cluster value → `agent_aihr` → maps to "AI HR"

#### Format 2: Short-format campaigns
```
{geo}-s-{cluster}-...
```
- Position `[2]` = cluster value

#### Exclusions
- Any campaign containing `crm` in any segment → excluded
- Campaigns with fewer than 3 hyphen-delimited parts → excluded
- Campaigns whose cluster value is not in the map → excluded

### Cluster Map (campaign cluster → report name)

| Cluster Value | Report Name |
|---|---|
| `agent_aicomp` | AI Comp |
| `agent_aiconstruction` | AI Construction |
| `agent_aifinance` | AI Finance |
| `agent_aihr` | AI HR |
| `agent_aiit` | AI IT |
| `agent_ailegal` | AI Legal |
| `agent_ailegal_contract` | AI Legal |
| `agent_aimarketing` | AI Marketing |
| `agent_ainote_taker` | AI Note Taker |
| `agent_aireal_estate` | AI Real Estate |
| `agent_aiwork_builder` | Work Agent |
| `agent_aiwork_agent` | Work Agent |
| `agent_aiwork_process` | AI Work Process |
| `agent_aigeneric` | AI Generic |
| `agent_aipmo` | AI PMO |

**Note:** Multiple cluster values can map to the same report name (e.g. `agent_aiwork_builder` and `agent_aiwork_agent` both → "Work Agent"; `agent_ailegal` and `agent_ailegal_contract` both → "AI Legal").

---

## 4. Metrics — How Each One Is Pulled

All metrics use **GAQL (Google Ads Query Language)** via Funnel Gate.

### 4.1 Performance Metrics (campaign level)

**Query:**
```sql
SELECT campaign.name, segments.date,
       metrics.cost_micros, metrics.impressions, metrics.clicks
FROM campaign
WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}'
  AND campaign.advertising_channel_type = 'SEARCH'
```

| Metric | Source Field | Transformation |
|---|---|---|
| **Spend** | `metrics.cost_micros` | Divided by 1,000,000 to get USD |
| **Impressions** | `metrics.impressions` | Raw integer |
| **Clicks** | `metrics.clicks` | Raw integer |

### 4.2 Conversion Metrics (campaign level)

**Query:**
```sql
SELECT campaign.name, segments.date,
       segments.conversion_action_name, metrics.all_conversions
FROM campaign
WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}'
  AND campaign.advertising_channel_type = 'SEARCH'
  AND segments.conversion_action_name IN ('Hard Signup (MCC)', 'Paying (MCC)')
```

| Metric | Conversion Action Name | Source Field |
|---|---|---|
| **Signups (Hard Signup)** | `Hard Signup (MCC)` | `metrics.all_conversions` |
| **Payers (Paying)** | `Paying (MCC)` | `metrics.all_conversions` |

**Important:** These conversion action names are **locked** (same as WoW dashboard, set by Tal). Uses `all_conversions` (not `conversions`), meaning cross-device and view-through are included.

### 4.3 Agents Created (campaign level)

**Query:**
```sql
SELECT campaign.name, segments.date,
       segments.conversion_action, metrics.all_conversions
FROM campaign
WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}'
  AND campaign.advertising_channel_type = 'SEARCH'
  AND segments.conversion_action = 'customers/{account_id}/conversionActions/7638407984'
```

| Metric | Conversion Action ID | Source Field |
|---|---|---|
| **Agent Created (AC)** | `7638407984` | `metrics.all_conversions` |

### 4.4 Ad Group Level Metrics

Same queries as above but from `ad_group` resource instead of `campaign`, with additional filters:
- `ad_group.status = 'ENABLED'`
- `campaign.status = 'ENABLED'` (except **AI Comp** which is exempt — its ad groups live inside general comp campaigns that may be paused)

### 4.5 Derived / Calculated Metrics

These are computed in the frontend JavaScript, not pulled from Google Ads:

| Metric | Formula | Notes |
|---|---|---|
| **CPS** (Cost Per Signup) | `spend / signups` | Shown as `$XX` |
| **CAC** (Customer Acquisition Cost) | `spend / payers` | `—` if payers = 0 |
| **CPAC** (Cost Per Agent Created) | `spend / agent_created` | `—` if AC = 0 |
| **CTR** (Click-Through Rate) | `clicks / impressions` | Shown as `X.X%` |
| **CR to SU** (Conversion Rate to Signup) | `signups / clicks` | Shown as `X.X%` |
| **%Work** (Work Signup %) | `work_signups / total_signups` | Indicates intent quality |
| **CVR Payer** (Conversion Rate to Paying) | `payers / signups` | Shown as `X.X%` |
| **AC %** (Agent Created Rate) | `agent_created / signups` | Shown as `X.X%` |
| **WoW Δ** (Week-over-Week Change) | `(this_week - last_week) / last_week` | Shown as `▲ X.X%` or `▼ X.X%` |

### 4.6 Work Signups (totalWorkSU)

`totalWorkSU` is stored per campaign in `CAMPAIGN_WEEKLY`. It represents the total number of signups from "work" (non-consumer) intent. It's distributed proportionally when filtering by date range using the signup ratio for the filtered period.

---

## 5. Week Definition & Aggregation

- **Week boundaries:** Monday through Sunday (Mon–Sun)
- `week_start_monday()` converts any date to the Monday of its week
- `week_end_sunday()` returns the Sunday for a given Monday
- All daily data is aggregated into weekly buckets server-side in `refresh.py`
- The frontend `filterData()` function supports partial-week filtering by computing overlap ratios

---

## 6. Dashboard Sections & Components

### 6.1 Section 1A: Overall Performance — Last Week

**Type:** KPI cards + weekly trend table

**KPI Cards (4):**
1. **Spend** — total spend across all agent campaigns, with WoW delta
2. **Impressions** — total impressions, with WoW delta
3. **Hard Signups** — total signups, with WoW delta
4. **Payers (since launch)** — cumulative payers since launch, with "+X this week"

**Weekly Trend Table:**
- Columns: Week | Spend | Δ | Impressions | Δ | Signups | Δ | CPS | Payers (new) | CAC | Agent Created | Δ | CPAC
- Shows last 6 weeks by default; "Show All Weeks" button reveals all
- Aggregates all campaigns per week

### 6.2 Section 1B: Funnel & Paying Analysis

**Type:** Interactive filterable table with date inputs + funnel bar

**Date Filter:**
- Two date inputs (From/To), defaults to last 7 days
- "All Data" button resets to full date range (since `2026-05-06`)
- Filter applies to both the funnel summary bar and the per-campaign table

**Funnel Summary Bar:**
- Impressions → CTR → Clicks → CR to Signup → Signups → %Work → Work SU → CVR Paying → Payers → AC % → Agents
- Shows conversion rates between each funnel step

**Per-Campaign Table:**
- Columns: Campaign | Spend | Imp | CTR | CR to SU | Signups | CPS | Work SU | %Work | Paying | CAC | CVR Payer | Agent Created | AC % | CPAC
- Sorted by spend (descending)
- Dynamically filtered by date range
- Reads from `CAMPAIGN_WEEKLY` JS data object

**Observations Grid (4 cards):**
1. 📉 Click to signup drops — highlights lowest/highest CR campaigns
2. 🎯 %Work signals intent quality — highlights %Work outliers
3. 💰 CVR Paying gap — highlights top payer converters
4. 🤖 Agent Created outlier — highlights highest AC rate campaigns

### 6.3 Section 2: Per-Campaign Detail

**Type:** Individual campaign cards with KPI grids + weekly trend tables + ad group breakdowns

**Organization:** Grouped by Google Ads account:
- **Main (3746504118):** Work Agent, AI Comp, AI HR, AI IT, AI Legal, AI Finance, AI Note Taker, AI Real Estate, AI Work Process
- **Verticals (6629846296):** AI Marketing, AI Construction
- **Standalone:** AI PMO

**Each campaign card contains:**
1. **Campaign name** with optional badge (`new` or `restructured`)
2. **KPI grid (4 cards):** Spend, Impressions, Hard Signups, Payers — all with WoW deltas
3. **Weekly trend table:** Same columns as overall table, but for this campaign only
4. **Ad group breakdown table:** Ad Group | Spend | Imp | Clicks | Signups | Payers | AC
   - Uses `AG_WEEKLY` data (dynamic filtering by date range)
   - `data-camp` attribute links the table to its AG_WEEKLY key
   - Ad groups with similar names (e.g. `AI Ads` / `ai_Ads`) are merged by normalized name

**Ad group table data-camp keys:**
| Report Name | data-camp Key |
|---|---|
| Work Agent | `work_agent` |
| AI Comp | `aicomp` |
| AI HR | `aihr` |
| AI IT | `aiit` |
| AI Legal | `ailegal` |
| AI Finance | `aifinance` |
| AI Note Taker | `ainote_taker` |
| AI Real Estate | `aireal_estate` |
| AI Work Process | `aiwork_process` |
| AI Marketing | `aimarketing` |
| AI Construction | `aiconstruction` |
| AI PMO | `aipmo` |

### 6.4 Footer

Static note explaining:
- Date range covered (10 weeks)
- That AI Comp includes comp1 agent ad groups from Jun 22
- That AI Legal includes ailegal_contract
- New campaigns detected
- Conversion methodology (all_conversions_by_conversion_date, cost_micros / 1M)
- Payers column semantics (weekly = new per week; funnel = cumulative since launch)

---

## 7. JS Data Structures

### CAMPAIGN_WEEKLY

```js
const CAMPAIGN_WEEKLY = {
  "Campaign Name": {
    "totalClicks": <int>,        // lifetime clicks (used for CTR proportioning)
    "totalWorkSU": <float>,      // lifetime work signups (used for %Work proportioning)
    "weeks": [
      {
        "start": "YYYY-MM-DD",   // Monday
        "end": "YYYY-MM-DD",     // Sunday
        "spend": <int>,          // rounded USD
        "imp": <int>,
        "signups": <float>,
        "payers": <float>,
        "ac": <float>            // agents created
      },
      // ... one entry per week
    ]
  },
  // ... one entry per campaign
};
```

### AG_WEEKLY

```js
var AG_WEEKLY = {
  "data_camp_key": {             // e.g. "aihr", "work_agent"
    "Ad Group Name": [           // array of weekly data, same structure as weeks
      {
        "start": "YYYY-MM-DD",
        "end": "YYYY-MM-DD",
        "spend": <float>,        // NOT rounded (precise dollars+cents)
        "imp": <int>,
        "clicks": <int>,
        "signups": <float>,
        "payers": <float>,
        "ac": <float>
      },
      // ... one entry per week
    ],
    // ... one entry per ad group
  },
  // ... one entry per campaign
};
```

---

## 8. Refresh Process

### When

- **Trigger:** Manual run of `refresh.py` (currently run by Nymeria agent)
- **Schedule:** Typically weekly (Monday after the week ends), or on-demand
- **Duration:** ~2-3 minutes (API calls to 5 accounts)

### How

1. `refresh.py` queries all 5 Google Ads accounts via Funnel Gate
2. Campaign names are parsed through `extract_agent()` to determine which agent they belong to
3. Daily data is aggregated into Monday-Sunday weekly buckets
4. `CAMPAIGN_WEEKLY` JS object in `index.html` is replaced via regex
5. Ad group breakdown HTML tables are updated per campaign
6. Title date is updated
7. Changes are committed and pushed to `main` branch
8. GitHub Pages auto-deploys within ~30 seconds

### What refresh.py does NOT update

- Overall KPI cards (Section 1A header cards) — these are **static HTML**, manually updated
- WoW delta arrows/percentages in the header — static HTML
- Observation cards (Section 1B) — static HTML
- Per-campaign KPI cards — static HTML
- `AG_WEEKLY` JS data object — this is updated separately (via `transform.py` or manual edit)

---

## 9. File Structure

```
monday-agent-growth-report/
├── index.html          # The entire dashboard (HTML + CSS + JS + data)
├── refresh.py          # Data refresh script (pulls from Google Ads)
├── transform.py        # AG_WEEKLY data transformer
├── sort_campaigns.py   # Utility for reordering campaigns
├── dashboard-spec.md   # This file
├── weekly-report.html  # (legacy)
└── rsa-report.html     # (legacy)
```

---

## 10. Visual Design

- **Theme:** Dark mode (#0f0f0f background)
- **Color palette:** Green (#1D9E75) for positive deltas, Red (#D85A30) for negative, Amber (#eda100) for warnings
- **Typography:** System fonts (-apple-system stack), 13px base
- **Layout:** Max-width 1200px, centered
- **Tables:** Alternating row backgrounds, right-aligned numeric columns
- **KPI cards:** 4-column grid with label, value, and delta

---

## 11. Adding a New Campaign

To add a new agent campaign to the dashboard:

1. **refresh.py:** Add the cluster value → report name mapping to `AGENT_CLUSTER_MAP`
   ```python
   "agent_newcampaign": "AI New Campaign",
   ```

2. **index.html:** Add a per-campaign detail section in the appropriate account group:
   - Campaign card with KPI grid (4 cards: Spend, Impressions, Hard Signups, Payers)
   - Weekly trend table
   - Ad group breakdown table with `data-camp="newcampaign"` attribute

3. **Run refresh.py** to populate `CAMPAIGN_WEEKLY` with real data

4. **Update this spec** (`dashboard-spec.md`) with the new campaign in the cluster map table and data-camp keys table

---

## 12. Adding a New Metric

To add a new metric column:

1. **If it's a new Google Ads metric:** Add the GAQL field to the appropriate query in `refresh.py`, include it in the weekly data structure, and update `build_campaign_weekly()`

2. **If it's a derived metric:** Add the calculation formula to the frontend JS `render()` or `filterData()` function

3. **Update column headers** in both the overall trend table and per-campaign trend tables

4. **Update this spec** with the new metric definition and formula

---

## 13. Changelog

| Date | Change |
|---|---|
| 2026-08-26 | Added AI PMO campaign (mapped from `agent_aipmo` cluster). Added CPAC column to funnel table. Added this spec file. |
| 2026-08-24 | Weekly refresh: data through Aug 23, 2026 |
| 2026-07-13 | Added AI Finance, AI Note Taker, AI Real Estate, AI Work Process, AI Construction campaigns |
| 2026-06-22 | AI Comp restructured to use agent ad groups from comp1 campaigns |
| 2026-06-15 | Initial dashboard launch with Work Agent, AI HR, AI IT, AI Legal, AI Marketing |
