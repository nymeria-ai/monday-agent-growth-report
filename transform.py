#!/usr/bin/env python3
"""
Transform: remove Δ from Signups/AC, add Δ to CPS/CPAC.
Then sort per-campaign blocks alphabetically.
"""
import re

with open('/Users/diegomalamute/repos/monday-agent-growth-report/index.html', 'r') as f:
    content = f.read()

# ── 1. Fix headers ──

# Overall trend table header
content = content.replace(
    '<th>Signups</th><th>Δ</th><th class="kpi-hi">CPS</th><th>Payers (new)</th><th>CAC</th>\n'
    '        <th>Agent Created</th><th>Δ</th><th class="kpi-hi">CPAC</th>',
    '<th>Signups</th><th class="kpi-hi">CPS</th><th>Δ</th><th>Payers (new)</th><th>CAC</th>\n'
    '        <th>Agent Created</th><th class="kpi-hi">CPAC</th><th>Δ</th>'
)

# Per-campaign headers
content = content.replace(
    '<th>Signups</th><th>Δ</th><th class="kpi-hi">CPS</th><th>Payers</th><th>CAC</th>\n'
    '                <th>Agent Created</th><th>Δ</th><th class="kpi-hi">CPAC</th>',
    '<th>Signups</th><th class="kpi-hi">CPS</th><th>Δ</th><th>Payers</th><th>CAC</th>\n'
    '                <th>Agent Created</th><th class="kpi-hi">CPAC</th><th>Δ</th>'
)

# ── 2. Transform data rows ──

def parse_dollar(s):
    s = s.strip().replace('$', '').replace(',', '')
    if s in ('—', ''):
        return None
    try:
        return float(s)
    except:
        return None

def make_cost_delta(curr_str, prev_str):
    """Cost delta: decrease=good(green ▼), increase=bad(red ▲)."""
    curr = parse_dollar(curr_str)
    prev = parse_dollar(prev_str)
    if curr is None or prev is None or prev == 0:
        return '<td><span class="neu">—</span></td>'
    pct = ((curr - prev) / prev) * 100
    if abs(pct) < 0.05:
        return '<td><span class="neu">– 0.0%</span></td>'
    elif pct > 0:
        return f'<td><span class="dn">▲ {abs(pct):.1f}%</span></td>'
    else:
        return f'<td><span class="up">▼ {abs(pct):.1f}%</span></td>'

def extract_text(td_html):
    """Get text content from td, handling nested spans."""
    # Remove tags, get text
    text = re.sub(r'<[^>]+>', '', td_html)
    return text.strip()

td_re = re.compile(r'<td[^>]*>(?:[^<]*(?:<[^/][^>]*>[^<]*</[^>]*>)*[^<]*)</td>')

def extract_cells(row_html):
    """Extract all td cells from a row."""
    return td_re.findall(row_html)

def transform_trend_table_tbody(tbody_html):
    """Transform a tbody: remove signups/AC deltas, add CPS/CPAC deltas."""
    row_re = re.compile(r'(<tr[^>]*>)(.*?)(</tr>)', re.DOTALL)
    rows = list(row_re.finditer(tbody_html))
    
    if not rows:
        return tbody_html
    
    prev_cps = None
    prev_cpac = None
    result = tbody_html
    offset = 0
    
    for m in rows:
        tr_open = m.group(1)
        row_content = m.group(2)
        tr_close = m.group(3)
        
        cells = extract_cells(tr_open + row_content + tr_close)
        
        # Must have exactly 13 cells (original format)
        if len(cells) != 13:
            continue
        
        # Original order:
        # 0:Week 1:Spend 2:SpendΔ 3:Imp 4:ImpΔ 5:Signups 6:SignupsΔ 
        # 7:CPS 8:Payers 9:CAC 10:AC 11:ACΔ 12:CPAC
        
        cps_text = extract_text(cells[7])
        cpac_text = extract_text(cells[12])
        
        cps_delta = make_cost_delta(cps_text, str(prev_cps) if prev_cps else '—')
        cpac_delta = make_cost_delta(cpac_text, str(prev_cpac) if prev_cpac else '—')
        
        prev_cps = cps_text if cps_text != '—' else None
        prev_cpac = cpac_text if cpac_text != '—' else None
        
        # New order: remove cells[6] (signupsΔ) and cells[11] (ACΔ)
        # Add cps_delta after cells[7], cpac_delta after cells[12]
        new_cells = [
            cells[0],    # Week
            cells[1],    # Spend
            cells[2],    # SpendΔ
            cells[3],    # Imp
            cells[4],    # ImpΔ
            cells[5],    # Signups
            cells[7],    # CPS
            cps_delta,   # CPSΔ
            cells[8],    # Payers
            cells[9],    # CAC
            cells[10],   # AC
            cells[12],   # CPAC
            cpac_delta,  # CPACΔ
        ]
        
        # Detect indentation from original row
        indent = '\n        '
        
        # Group cells like original formatting
        new_row_content = (
            f"{indent}{new_cells[0]}"
            f"{indent}{new_cells[1]}{new_cells[2]}"
            f"{indent}{new_cells[3]}{new_cells[4]}"
            f"{indent}{new_cells[5]}"
            f"{indent}{new_cells[6]}{new_cells[7]}"
            f"{indent}{new_cells[8]}"
            f"{indent}{new_cells[9]}"
            f"{indent}{new_cells[10]}"
            f"{indent}{new_cells[11]}{new_cells[12]}"
            f"\n    "
        )
        
        new_row = tr_open + new_row_content + tr_close
        
        # Replace in result
        old_start = m.start() + offset
        old_end = m.end() + offset
        old_row = result[old_start:old_end]
        result = result[:old_start] + new_row + result[old_end:]
        offset += len(new_row) - len(old_row)
    
    return result

# Find trend tables and transform their tbodies
trend_table_re = re.compile(
    r'(<table[^>]*(?:class="trend-table"|id="overall-trend-table")[^>]*>)(.*?)(</table>)',
    re.DOTALL
)

def transform_table(m):
    table_open = m.group(1)
    table_content = m.group(2)
    table_close = m.group(3)
    
    # Find and transform tbody
    tbody_re = re.compile(r'(<tbody>)(.*?)(</tbody>)', re.DOTALL)
    
    def transform_tbody_match(tm):
        full_tbody = tm.group(0)
        return transform_trend_table_tbody(full_tbody)
    
    new_content = tbody_re.sub(transform_tbody_match, table_content)
    return table_open + new_content + table_close

content = trend_table_re.sub(transform_table, content)

# ── 3. Sort campaign blocks alphabetically ──

marker = '<div class="section-label">Per-Campaign Detail</div>'
marker_pos = content.find(marker)

if marker_pos != -1:
    def find_all_camp_blocks(html, start_pos):
        blocks = []
        pos = start_pos
        first_start = None
        last_end = None
        
        while True:
            block_start = html.find('<div class="camp-block">', pos)
            if block_start == -1:
                break
            if first_start is None:
                first_start = block_start
            
            depth = 0
            i = block_start
            while i < len(html):
                if html[i:i+4] == '<div':
                    depth += 1
                elif html[i:i+6] == '</div>':
                    depth -= 1
                    if depth == 0:
                        block_end = i + 6
                        blocks.append(html[block_start:block_end])
                        pos = block_end
                        last_end = block_end
                        break
                i += 1
            else:
                break
        
        return blocks, first_start, last_end
    
    blocks, region_start, region_end = find_all_camp_blocks(content, marker_pos)
    
    def get_camp_name(block):
        m = re.search(r'<div class="section-label">([^<]+)', block)
        return m.group(1).strip() if m else ''
    
    print(f"Found {len(blocks)} campaign blocks")
    blocks.sort(key=lambda b: get_camp_name(b).lower())
    print("Sorted:", [get_camp_name(b) for b in blocks])
    
    separator = '\n\n    '
    new_region = separator.join(blocks)
    content = content[:region_start] + new_region + content[region_end:]

with open('/Users/diegomalamute/repos/monday-agent-growth-report/index.html', 'w') as f:
    f.write(content)

print("Done!")
