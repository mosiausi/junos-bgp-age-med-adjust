#!/usr/bin/env python3
import subprocess

CONFIG_FILE = "/var/tmp/auto_med.conf"

def run_cli_command(cmd):
    proc = subprocess.run(["cli", "-c", cmd], capture_output=True, text=True)
    print(f"Running CLI command: {cmd}")
    print(f"STDOUT:\n{proc.stdout}")
    print(f"STDERR:\n{proc.stderr}")
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {proc.returncode}")

def main():
    # Use 'load set' because the config file contains 'set' commands, not hierarchical config
    cli_cmd = f"configure; load set {CONFIG_FILE}; commit; exit"
    try:
        run_cli_command(cli_cmd)
        print("Configuration loaded and committed successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
