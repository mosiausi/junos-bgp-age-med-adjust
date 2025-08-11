#!/usr/bin/env python3

import subprocess
import re

def run_cli(cmd):
    proc = subprocess.run(["cli", "-c", cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"CLI command failed: {cmd}\n{proc.stderr}")
    return proc.stdout

def parse_age_to_seconds(age_str):
    h, m, s = map(int, age_str.split(":"))
    return h*3600 + m*60 + s

def main():
    NEIGHBORS = ["172.30.101.1", "172.30.102.1"]
    print(f"Comparing BGP route ages from neighbors: {', '.join(NEIGHBORS)}")

    output = run_cli("show route table inet.0 protocol bgp")

    neighbor_routes = {nbr:{} for nbr in NEIGHBORS}
    prefix = None

    for line in output.splitlines():
        line = line.rstrip()
        # Match prefix + neighbor info on same line
        m_full = re.match(r'^(\S+/\d+)\s+.*\[BGP/\d+\]\s+(\d{2}:\d{2}:\d{2}),.*from\s+(\d+\.\d+\.\d+\.\d+)', line)
        if m_full:
            prefix = m_full.group(1)
            age_str = m_full.group(2)
            nbr_ip = m_full.group(3)
            if nbr_ip in NEIGHBORS:
                age_sec = parse_age_to_seconds(age_str)
                neighbor_routes[nbr_ip][prefix] = age_sec
            continue

        # Match prefix line only
        m_prefix = re.match(r'^(\S+/\d+)\s*$', line)
        if m_prefix:
            prefix = m_prefix.group(1)
            continue

        # Match neighbor route line indented
        m_nbr = re.search(r'\[BGP/\d+\]\s+(\d{2}:\d{2}:\d{2}),.*from\s+(\d+\.\d+\.\d+\.\d+)', line)
        if m_nbr and prefix:
            age_str = m_nbr.group(1)
            nbr_ip = m_nbr.group(2)
            if nbr_ip in NEIGHBORS:
                age_sec = parse_age_to_seconds(age_str)
                neighbor_routes[nbr_ip][prefix] = age_sec

    for nbr in NEIGHBORS:
        print(f"Neighbor {nbr}: {len(neighbor_routes[nbr])} prefixes")

    all_prefixes = set()
    for routes in neighbor_routes.values():
        all_prefixes.update(routes.keys())

    changes_needed = False
    term_num = 1
    print("\n### Generated Junos policy statements to de-prioritize older routes ###")
    for prefix in sorted(all_prefixes):
        ages = {nbr: neighbor_routes[nbr].get(prefix) for nbr in NEIGHBORS if prefix in neighbor_routes[nbr]}
        if len(ages) < 2:
            continue
        max_nbr = max(ages, key=ages.get)
        min_nbr = min(ages, key=ages.get)
        if ages[max_nbr] > ages[min_nbr]:
            changes_needed = True
            print(f"{prefix}: Older from {max_nbr} ({ages[max_nbr]} sec) vs {min_nbr} ({ages[min_nbr]} sec)")
            print(f"set policy-options policy-statement AUTO-MED term {term_num} from neighbor {max_nbr}")
            print(f"set policy-options policy-statement AUTO-MED term {term_num} from route-filter {prefix} exact")
            print(f"set policy-options policy-statement AUTO-MED term {term_num} then reject\n")
            term_num += 1

    print("set policy-options policy-statement AUTO-MED then default-action accept")
    print("\n# Then apply with:")
    print("set protocols bgp group INTERNET_RR import AUTO-MED\n")

    if not changes_needed:
        print("No MED adjustments needed.")

if __name__ == "__main__":
    main()
