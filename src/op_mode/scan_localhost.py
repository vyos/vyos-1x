#!/usr/bin/env python3

import subprocess

def scan_localhost():
    try:
        # Run the nmap command to list open TCP ports on localhost
        result = subprocess.run(
            ['nmap', '-sT', 'localhost'],
            capture_output=True, text=True, check=True
        )
        output = result.stdout
        
        # Extract only the lines containing port information
        start_extracting = False
        for line in output.split('\n'):
            if line.startswith("PORT"):
                start_extracting = True
            if start_extracting:
                if line.startswith("Nmap done:"):
                    break
                print(line)

    except subprocess.CalledProcessError as e:
        print(f"Error executing nmap command: {e}")

if __name__ == "__main__":
    scan_localhost()
