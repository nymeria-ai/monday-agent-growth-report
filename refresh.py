#!/usr/bin/env python3
"""
Agent Growth Report — Refresh Script
Pulls agent campaign data from all 5 Google Ads accounts via Funnel Gate,
aggregates by Sun-Sat week, and updates CAMPAIGN_WEEKLY in index.html.

Uses same metric definitions as WoW dashboard (locked by Tal).
"""
import json
import subprocess
import sys
import re
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
INDEX_HTML = SCRIPT_DIR / "index.html"
FUNNEL_GATE_URL = "http://localhost:9400/execute"

ACCOUNTS = {
    "3746504118": "Main",
    "6629846296": "Verticals",
    "9194503735": "Verticals2",
    "9441310809": "Locals",
    "6073520942": "Brand",
}

START_DATE = "2026-06-01"

# Conversion actions — LOCKED (same as WoW dashboard)
HARD_SIGNUP_ACTION = "Hard Signup (MCC)"
PAYER_ACTION = "Paying (MCC)"
AGENTS_CREATED_CT_ID = "7638407984"

# Campaign cluster value → Agent report name
AGENT_CLUSTER_MAP = {
    "agent_aicomp": "AI Comp",
    "agent_aiconstruction": "AI Construction",
    "agent_aifinance": "AI Finance",
    "agent_aihr": "AI HR",
    "agent_aiit": "AI IT",
    "agent_ailegal": "AI Legal",
    "agent_ailegal_contract": "AI Legal",
    "agent_aimarketing": "AI Marketing",
    "agent_ainote_taker": "AI Note Taker",
    "agent_aireal_estate": "AI Real Estate",
    "agent_aiwork_builder": "Work Builder",
    "agent_aiwork_process": "AI Work Process",
    "agent_aigeneric": "AI Generic",
}


def extract_agent(campaign_name: str) -> str | None:
    """Extract agent report name from campaign name. Returns None if not an agent campaign."""
    base_name = campaign_name.split(" ")[0] if " " in campaign_name else campaign_name
    parts = base_name.split("-")
    parts_lower = [p.lower() for p in parts]

    # CRM exclusion
    if any("crm" in p for p in parts_lower):
        return None

    if len(parts) < 3:
        return None

    # Detect format
    if len(parts) >= 6 and parts[2].lower() == "prm":
        cluster_val = parts[5].lower()
    elif len(parts) >= 3 and parts[1].lower() == "s":
        cluster_val = parts[2].lower()
    else:
        return None

    return AGENT_CLUSTER_MAP.get(cluster_val)


def week_start_monday(date_str: str) -> str:
    """Convert YYYY-MM-DD to the Monday that starts its Mon-Sun week."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")


def week_end_sunday(monday_str: str) -> str:
    """Given a Monday, return the Sunday end of that week."""
    d = datetime.strptime(monday_str, "%Y-%m-%d")
    return (d + timedelta(days=6)).strftime("%Y-%m-%d")


def run_gaql(customer_id: str, query: str) -> list:
    """Execute a GAQL query via Funnel Gate."""
    payload = {
        "requester": "nymeria",
        "action": "gaql_query",
        "platform": "google_ads",
        "scope": {
            "customer_id": customer_id,
            "query": query,
        },
        "trail": {"reasoning": "Agent growth report weekly refresh"},
        "skill_name": "agent-growth-report-refresh",
        "initiator": {"name": "Nymeria", "context": "Agent growth report refresh"},
    }
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", FUNNEL_GATE_URL,
         "-H", "Content-Type: application/json",
         "-d", json.dumps(payload)],
        capture_output=True, text=True, timeout=120
    )
    data = json.loads(result.stdout)
    if "error" in data:
        print(f"  ERROR for {customer_id}: {data['error']}", file=sys.stderr)
        return []
    return data.get("result", {}).get("results", [])


def pull_data():
    """Pull agent campaign data from all accounts."""
    today = datetime.now()
    end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"🔄 Agent Growth Report Refresh")
    print(f"{'='*50}")
    print(f"Pulling data from {START_DATE} to {end_date}\n")

    # {agent_name: {week_monday: {spend, imp, clicks, signups, payers, ac}}}
    agent_data = defaultdict(lambda: defaultdict(lambda: {
        "spend": 0, "imp": 0, "clicks": 0, "signups": 0, "payers": 0, "ac": 0
    }))

    # {agent_name: {ag_id: {name, spend, imp, clicks, signups, payers, ac}}}
    ag_data = defaultdict(lambda: defaultdict(lambda: {
        "name": "", "spend": 0, "imp": 0, "clicks": 0, "signups": 0, "payers": 0, "ac": 0
    }))

    for acct_id, acct_name in ACCOUNTS.items():
        print(f"=== {acct_name} ({acct_id}) ===")

        # Performance metrics
        perf_query = (
            f"SELECT campaign.name, segments.date, "
            f"metrics.cost_micros, metrics.impressions, metrics.clicks "
            f"FROM campaign "
            f"WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}' "
            f"AND campaign.advertising_channel_type = 'SEARCH'"
        )
        print(f"  Pulling performance metrics...")
        perf_rows = run_gaql(acct_id, perf_query)
        print(f"  Got {len(perf_rows)} performance rows")

        # Conversions (signups + payers)
        conv_query = (
            f"SELECT campaign.name, segments.date, "
            f"segments.conversion_action_name, metrics.all_conversions "
            f"FROM campaign "
            f"WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}' "
            f"AND campaign.advertising_channel_type = 'SEARCH' "
            f"AND segments.conversion_action_name IN ("
            f"'{HARD_SIGNUP_ACTION}', '{PAYER_ACTION}')"
        )
        print(f"  Pulling conversion metrics...")
        conv_rows = run_gaql(acct_id, conv_query)
        print(f"  Got {len(conv_rows)} conversion rows")

        # Agents Created
        agents_query = (
            f"SELECT campaign.name, segments.date, segments.conversion_action, metrics.all_conversions "
            f"FROM campaign "
            f"WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}' "
            f"AND campaign.advertising_channel_type = 'SEARCH' "
            f"AND segments.conversion_action = 'customers/{acct_id}/conversionActions/{AGENTS_CREATED_CT_ID}'"
        )
        print(f"  Pulling agents_created metrics...")
        agents_rows = run_gaql(acct_id, agents_query)
        print(f"  Got {len(agents_rows)} agents_created rows")

        # Ad group level performance (for breakdown tables)
        # Filter: ad_group ENABLED + campaign ENABLED (except AI Comp — lives in general comp campaigns)
        ag_status_filter = "AND campaign.status = 'ENABLED' AND ad_group.status = 'ENABLED'"
        ag_perf_query = (
            f"SELECT campaign.name, campaign.status, ad_group.id, ad_group.name, "
            f"metrics.cost_micros, metrics.impressions, metrics.clicks "
            f"FROM ad_group "
            f"WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}' "
            f"AND campaign.advertising_channel_type = 'SEARCH' "
            f"AND ad_group.status = 'ENABLED'"
        )
        print(f"  Pulling ad group performance...")
        ag_perf_rows = run_gaql(acct_id, ag_perf_query)
        print(f"  Got {len(ag_perf_rows)} ad group perf rows")

        # Ad group level conversions (ad_group ENABLED; campaign check in processing)
        ag_conv_query = (
            f"SELECT campaign.name, campaign.status, ad_group.id, ad_group.name, "
            f"segments.conversion_action_name, metrics.all_conversions "
            f"FROM ad_group "
            f"WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}' "
            f"AND campaign.advertising_channel_type = 'SEARCH' "
            f"AND ad_group.status = 'ENABLED' "
            f"AND segments.conversion_action_name IN ("
            f"'{HARD_SIGNUP_ACTION}', '{PAYER_ACTION}')"
        )
        print(f"  Pulling ad group conversions...")
        ag_conv_rows = run_gaql(acct_id, ag_conv_query)
        print(f"  Got {len(ag_conv_rows)} ad group conv rows")

        # Ad group level agents created (ad_group ENABLED; campaign check in processing)
        ag_ac_query = (
            f"SELECT campaign.name, campaign.status, ad_group.id, ad_group.name, "
            f"segments.conversion_action, metrics.all_conversions "
            f"FROM ad_group "
            f"WHERE segments.date BETWEEN '{START_DATE}' AND '{end_date}' "
            f"AND campaign.advertising_channel_type = 'SEARCH' "
            f"AND ad_group.status = 'ENABLED' "
            f"AND segments.conversion_action = 'customers/{acct_id}/conversionActions/{AGENTS_CREATED_CT_ID}'"
        )
        print(f"  Pulling ad group agents_created...")
        ag_ac_rows = run_gaql(acct_id, ag_ac_query)
        print(f"  Got {len(ag_ac_rows)} ad group AC rows")

        # Process performance
        for row in perf_rows:
            camp_name = row.get("campaign", {}).get("name", "")
            date = row.get("segments", {}).get("date", "")
            metrics = row.get("metrics", {})
            agent = extract_agent(camp_name)
            if agent is None:
                continue
            week = week_start_monday(date)
            agent_data[agent][week]["spend"] += float(metrics.get("costMicros", 0)) / 1_000_000
            agent_data[agent][week]["imp"] += int(metrics.get("impressions", 0))
            agent_data[agent][week]["clicks"] += int(metrics.get("clicks", 0))

        # Process conversions
        for row in conv_rows:
            camp_name = row.get("campaign", {}).get("name", "")
            date = row.get("segments", {}).get("date", "")
            conv_name = row.get("segments", {}).get("conversionActionName", "")
            metrics = row.get("metrics", {})
            agent = extract_agent(camp_name)
            if agent is None:
                continue
            week = week_start_monday(date)
            conversions = float(metrics.get("allConversions", 0))
            if conv_name == HARD_SIGNUP_ACTION:
                agent_data[agent][week]["signups"] += conversions
            elif conv_name == PAYER_ACTION:
                agent_data[agent][week]["payers"] += conversions

        # Process agents created
        for row in agents_rows:
            camp_name = row.get("campaign", {}).get("name", "")
            date = row.get("segments", {}).get("date", "")
            metrics = row.get("metrics", {})
            agent = extract_agent(camp_name)
            if agent is None:
                continue
            week = week_start_monday(date)
            agent_data[agent][week]["ac"] += float(metrics.get("allConversions", 0))

        # Process ad group performance (aggregate by ad group ID)
        # AI Comp exempt from campaign.status check (lives in general comp campaigns)
        CAMP_STATUS_EXEMPT = {"AI Comp"}
        for row in ag_perf_rows:
            camp_name = row.get("campaign", {}).get("name", "")
            camp_status = row.get("campaign", {}).get("status", "")
            agent = extract_agent(camp_name)
            if agent is None:
                continue
            if agent not in CAMP_STATUS_EXEMPT and camp_status != "ENABLED":
                continue
            ag_id = str(row.get("adGroup", {}).get("id", ""))
            ag_name = row.get("adGroup", {}).get("name", "")
            metrics = row.get("metrics", {})
            ag_data[agent][ag_id]["name"] = ag_name  # latest name wins
            ag_data[agent][ag_id]["spend"] += float(metrics.get("costMicros", 0)) / 1_000_000
            ag_data[agent][ag_id]["imp"] += int(metrics.get("impressions", 0))
            ag_data[agent][ag_id]["clicks"] += int(metrics.get("clicks", 0))

        # Process ad group conversions
        for row in ag_conv_rows:
            camp_name = row.get("campaign", {}).get("name", "")
            camp_status = row.get("campaign", {}).get("status", "")
            agent = extract_agent(camp_name)
            if agent is None:
                continue
            if agent not in CAMP_STATUS_EXEMPT and camp_status != "ENABLED":
                continue
            ag_id = str(row.get("adGroup", {}).get("id", ""))
            ag_name = row.get("adGroup", {}).get("name", "")
            conv_name = row.get("segments", {}).get("conversionActionName", "")
            conversions = float(row.get("metrics", {}).get("allConversions", 0))
            ag_data[agent][ag_id]["name"] = ag_name
            if conv_name == HARD_SIGNUP_ACTION:
                ag_data[agent][ag_id]["signups"] += conversions
            elif conv_name == PAYER_ACTION:
                ag_data[agent][ag_id]["payers"] += conversions

        # Process ad group agents created
        for row in ag_ac_rows:
            camp_name = row.get("campaign", {}).get("name", "")
            camp_status = row.get("campaign", {}).get("status", "")
            agent = extract_agent(camp_name)
            if agent is None:
                continue
            if agent not in CAMP_STATUS_EXEMPT and camp_status != "ENABLED":
                continue
            ag_id = str(row.get("adGroup", {}).get("id", ""))
            ag_name = row.get("adGroup", {}).get("name", "")
            ag_data[agent][ag_id]["name"] = ag_name
            ag_data[agent][ag_id]["ac"] += float(row.get("metrics", {}).get("allConversions", 0))

    return agent_data, ag_data


def build_campaign_weekly(agent_data: dict) -> dict:
    """Build CAMPAIGN_WEEKLY structure from raw agent data."""
    result = {}
    for agent_name in sorted(agent_data.keys()):
        weeks_dict = agent_data[agent_name]
        sorted_weeks = sorted(weeks_dict.keys())

        total_clicks = 0
        total_signups = 0
        weeks_list = []

        for monday in sorted_weeks:
            d = weeks_dict[monday]
            sunday = week_end_sunday(monday)
            total_clicks += d["clicks"]
            total_signups += d["signups"]
            weeks_list.append({
                "start": monday,
                "end": sunday,
                "spend": round(d["spend"]),
                "imp": d["imp"],
                "signups": round(d["signups"], 1),
                "payers": round(d["payers"], 1),
                "ac": round(d["ac"], 1),
            })

        result[agent_name] = {
            "totalClicks": total_clicks,
            "totalWorkSU": round(total_signups, 1),
            "weeks": weeks_list,
        }

    return result


def normalize_ag_name(name: str) -> str:
    """Normalize ad group name for merging: lowercase, underscores→spaces."""
    return name.lower().replace("_", " ").strip()


def pick_display_name(names: set) -> str:
    """Pick the cleanest display name from a set of variants (prefer spaces over underscores)."""
    for n in sorted(names, key=lambda x: (x.count("_"), -len(x))):
        if "_" not in n:
            return n
    return sorted(names)[0]


def merge_ag_by_name(ag_dict: dict) -> dict:
    """Merge ad groups with same normalized name (e.g. 'AI Ads' + 'ai_Ads')."""
    merged = {}  # normalized_name → {names: set, spend, imp, clicks, signups, payers, ac}
    for ag_id, d in ag_dict.items():
        norm = normalize_ag_name(d["name"] or f"AG {ag_id}")
        if norm not in merged:
            merged[norm] = {"names": set(), "spend": 0, "imp": 0, "clicks": 0,
                           "signups": 0, "payers": 0, "ac": 0}
        merged[norm]["names"].add(d["name"] or f"AG {ag_id}")
        for k in ("spend", "imp", "clicks", "signups", "payers", "ac"):
            merged[norm][k] += d[k]
    return merged


def build_ag_breakdown_html(agent_name: str, ag_dict: dict) -> str:
    """Build ad group breakdown HTML table for a campaign (merged by normalized name)."""
    if not ag_dict:
        return ""
    merged = merge_ag_by_name(ag_dict)
    sorted_ags = sorted(merged.items(), key=lambda x: -x[1]["spend"])
    rows = []
    for norm, d in sorted_ags:
        name = pick_display_name(d["names"])
        spend = f"${d['spend']:,.2f}" if d['spend'] < 1000 else f"${d['spend']:,.0f}"
        rows.append(
            f'<tr><td>{name}</td><td>{spend}</td><td>{d["imp"]:,}</td>'
            f'<td>{d["clicks"]:,}</td><td>{d["signups"]:.1f}</td>'
            f'<td>{d["payers"]:.1f}</td><td>{d["ac"]:.1f}</td></tr>'
        )
    table = (
        '<div class="kw-note"><strong>Ad group breakdown</strong>'
        '<table class="comp1-table ag-table">'
        '<thead><tr><th>Ad Group</th><th>Spend</th><th>Imp</th>'
        '<th>Clicks</th><th>Signups</th><th>Payers</th><th>AC</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )
    return table


def update_html(campaign_weekly: dict, ag_data: dict = None):
    """Update CAMPAIGN_WEEKLY in index.html, ad group breakdowns, and title date."""
    html = INDEX_HTML.read_text()

    # Update CAMPAIGN_WEEKLY line
    new_data = json.dumps(campaign_weekly, separators=(",", ":"))
    html = re.sub(
        r'var CAMPAIGN_WEEKLY\s*=\s*\{.*?\};',
        f'var CAMPAIGN_WEEKLY = {new_data};',
        html,
        flags=re.DOTALL
    )

    # Update ad group breakdown tables if ag_data provided
    if ag_data:
        for agent_name, ags in ag_data.items():
            new_table = build_ag_breakdown_html(agent_name, ags)
            # Replace existing ag-table for this campaign
            pattern = re.compile(
                r'(<div class="section-label">'
                + re.escape(agent_name)
                + r'.*?</div>.*?)'
                r'(<div class="kw-note"><strong>Ad group breakdown</strong>'
                r'<table class="comp1-table ag-table"[^>]*>.*?</table></div>)',
                re.DOTALL
            )
            html = pattern.sub(lambda m: m.group(1) + new_table, html)

    # Update title date
    today_str = datetime.now().strftime("%b %-d, %Y")
    html = re.sub(
        r'<title>Agent Weekly Growth Report — [^<]+</title>',
        f'<title>Agent Weekly Growth Report — {today_str}</title>',
        html
    )

    INDEX_HTML.write_text(html)
    print(f"\nUpdated index.html ({len(new_data):,} chars of CAMPAIGN_WEEKLY)")


def main():
    agent_data, ag_data = pull_data()

    print(f"\n📊 Summary: {len(agent_data)} agent campaigns")
    for name in sorted(agent_data.keys()):
        weeks = agent_data[name]
        total_spend = sum(w["spend"] for w in weeks.values())
        ag_count = len(ag_data.get(name, {}))
        print(f"  {name}: {len(weeks)} weeks, ${total_spend:,.0f} total spend, {ag_count} ad groups")

    campaign_weekly = build_campaign_weekly(agent_data)
    update_html(campaign_weekly, ag_data)

    # Git commit + push
    subprocess.run(["git", "add", "index.html"], cwd=SCRIPT_DIR)
    subprocess.run(
        ["git", "commit", "-m", f"Auto-refresh data {datetime.now().strftime('%Y-%m-%d')}"],
        cwd=SCRIPT_DIR, capture_output=True
    )
    subprocess.run(["git", "push"], cwd=SCRIPT_DIR, capture_output=True)
    print(f"Committed and pushed: Auto-refresh data {datetime.now().strftime('%Y-%m-%d')}")
    print(f"\n✅ Agent Growth Report refreshed and deployed!")


if __name__ == "__main__":
    main()
