#!/usr/bin/env python3
"""Sort per-campaign detail blocks alphabetically by campaign name."""
import re

with open('/Users/diegomalamute/repos/monday-agent-growth-report/index.html', 'r') as f:
    content = f.read()

marker = '<div class="section-label">Per-Campaign Detail</div>'
marker_pos = content.find(marker)
if marker_pos == -1:
    print("ERROR: Per-Campaign Detail section not found")
    exit(1)

# Find ALL camp-blocks after the marker
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
        
        # Count div nesting to find the matching </div>
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
print(f"Found {len(blocks)} campaign blocks")

def get_camp_name(block):
    m = re.search(r'<div class="section-label">([^<]+)', block)
    return m.group(1).strip() if m else ''

for b in blocks:
    print(f"  - {get_camp_name(b)}")

blocks.sort(key=lambda b: get_camp_name(b).lower())

print("\nSorted order:")
for b in blocks:
    print(f"  - {get_camp_name(b)}")

# Replace region with sorted blocks, preserving original spacing pattern
separator = '\n\n    '
new_region = separator.join(blocks)

# Get the whitespace before the first block
pre_ws = content[content.rfind('\n', 0, region_start):region_start]
if not pre_ws.startswith('\n'):
    pre_ws = '\n    '

content = content[:region_start] + new_region + content[region_end:]

with open('/Users/diegomalamute/repos/monday-agent-growth-report/index.html', 'w') as f:
    f.write(content)

print("\nDone!")
