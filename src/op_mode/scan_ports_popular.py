#!/usr/bin/env python3

import subprocess
import sys

def scan_popular_ports(host):
    # List of popular ports to scan
    popular_ports = [
        20, 21, 22, 23, 25, 53, 80, 110, 123, 135, 137, 138, 139, 143, 161, 162,
        179, 389, 443, 445, 465, 514, 587, 993, 995, 1080, 1433, 1434, 1521, 1723,
        3306, 3389, 5060, 5432, 5900, 5938, 8080, 8443, 8888
    ]
    
    # Create a comma-separated string of ports
    ports_str = ",".join(map(str, popular_ports))
    
    try:
        # Run the nmap command to scan the specified ports on the given host
        result = subprocess.run(
            ['nmap', '-p', ports_str, host],
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
    if len(sys.argv) != 2:
        print("Usage: python scan_popular_ports.py <IP>")
        sys.exit(1)

    remote_host = sys.argv[1]
    scan_popular_ports(remote_host)
