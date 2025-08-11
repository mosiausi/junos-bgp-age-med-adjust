#!/usr/bin/env python3
"""
===============================================================================
BGP Route Age Comparator & AUTO-MED Policy Generator
Author: Moshiko Nayman
Version: 1.0
===============================================================================
Description:
    Compares BGP route ages for a given set of neighbors and generates Junos
    policy statements to de-prioritize older routes by rejecting them via
    the AUTO-MED policy. Optionally saves the configuration to a file
    for later loading and committing on the router.

Disclaimer:
    This script is provided "AS IS" without warranties or guarantees of any kind.
    The author accepts no responsibility or liability for any damage, downtime,
    or misconfiguration that may result from its use. Use entirely at your own risk.
===============================================================================
"""

import subprocess
import re

def run_cli(cmd):
    proc = subprocess.run(["cli", "-c", cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"CLI command failed: {cmd}\n{proc.stderr}")
    return proc.stdout

def parse_age_to_seconds(age_str):
    h, m, s = map(int, age_str.split(":"))
    return h * 3600 + m * 60 + s

def main():
    NEIGHBORS = ["172.30.101.1", "172.30.102.1"]
    print(f"Comparing BGP route ages from neighbors: {', '.join(NEIGHBORS)}")

    output = run_cli("show route table inet.0 protocol bgp")
    neighbor_routes = {nbr: {} for nbr in NEIGHBORS}
    prefix = None

    for line in output.splitlines():
        line = line.rstrip()
        m_full = re.match(r'^(\S+/\d+)\s+.*\[BGP/\d+\]\s+(\d{2}:\d{2}:\d{2}),.*from\s+(\d+\.\d+\.\d+\.\d+)', line)
        if m_full:
            prefix, age_str, nbr_ip = m_full.groups()
            if nbr_ip in NEIGHBORS:
                neighbor_routes[nbr_ip][prefix] = parse_age_to_seconds(age_str)
            continue

        m_prefix = re.match(r'^(\S+/\d+)\s*$', line)
        if m_prefix:
            prefix = m_prefix.group(1)
            continue

        m_nbr = re.search(r'\[BGP/\d+\]\s+(\d{2}:\d{2}:\d{2}),.*from\s+(\d+\.\d+\.\d+\.\d+)', line)
        if m_nbr and prefix:
            age_str, nbr_ip = m_nbr.groups()
            if nbr_ip in NEIGHBORS:
                neighbor_routes[nbr_ip][prefix] = parse_age_to_seconds(age_str)

    changes_needed = False
    term_num = 1
    config_lines = ["delete policy-options policy-statement AUTO-MED"]

    print("\n### Generated Junos policy statements to de-prioritize older routes ###")
    for prefix in sorted({k for v in neighbor_routes.values() for k in v}):
        ages = {nbr: neighbor_routes[nbr].get(prefix) for nbr in NEIGHBORS if prefix in neighbor_routes[nbr]}
        if len(ages) < 2:
            continue
        max_nbr = max(ages, key=ages.get)
        min_nbr = min(ages, key=ages.get)
        if ages[max_nbr] > ages[min_nbr]:
            changes_needed = True
            print(f"{prefix}: Older from {max_nbr} ({ages[max_nbr]} sec) vs {min_nbr} ({ages[min_nbr]} sec)")
            config_lines.append(f"set policy-options policy-statement AUTO-MED term {term_num} from neighbor {max_nbr}")
            config_lines.append(f"set policy-options policy-statement AUTO-MED term {term_num} from route-filter {prefix} exact")
            config_lines.append(f"set policy-options policy-statement AUTO-MED term {term_num} then reject\n")
            print(f"set policy-options policy-statement AUTO-MED term {term_num} from neighbor {max_nbr}")
            print(f"set policy-options policy-statement AUTO-MED term {term_num} from route-filter {prefix} exact")
            print(f"set policy-options policy-statement AUTO-MED term {term_num} then reject\n")
            term_num += 1

    if changes_needed:
        config_lines.append("set policy-options policy-statement AUTO-MED then default-action accept")
        config_lines.append("set protocols bgp group INTERNET_RR import AUTO-MED")

        print("set policy-options policy-statement AUTO-MED then default-action accept")
        print("\n# Apply policy with:")
        print("set protocols bgp group INTERNET_RR import AUTO-MED\n")

        config_path = "/var/tmp/auto_med.conf"
        with open(config_path, "w") as f:
            f.write("\n".join(config_lines) + "\n")
        print(f"Configuration saved to {config_path}")
        print(f"Run 'configure; load {config_path}; commit' to apply changes.")
    else:
        print("No MED adjustments needed.")

if __name__ == "__main__":
    main()
