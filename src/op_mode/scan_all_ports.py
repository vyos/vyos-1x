#!/usr/bin/env python3

import subprocess
import argparse

def scan_ports(host):
    # Define the command to execute
    command = ['nmap', '-p-', '-T4', '--min-rate=5000', '--max-retries=1', '--host-timeout=30s', host]
    
    try:
        # Execute the command and capture the result
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # Extract and print only the lines containing port information
        output = result.stdout
        start_extracting = False
        for line in output.split('\n'):
            if line.startswith("PORT"):
                start_extracting = True
            if start_extracting:
                if line.startswith("Nmap done:"):
                    break
                print(line)
                
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")

if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser(description='Scan all ports on a remote host using T4 timing template with high rate and reduced retries.')
    parser.add_argument('host', type=str, help='IP address or domain name of the host to scan')
    
    # Parse the arguments
    args = parser.parse_args()
    
    # Perform the scan
    scan_ports(args.host)
