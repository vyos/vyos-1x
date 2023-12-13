#!/usr/bin/env python3

import sys
from argparse import ArgumentParser
from vyos.remote import download

parser = ArgumentParser()
parser.add_argument('--local-file', help='local file', required=True)
parser.add_argument('--remote-path', help='remote path', required=True)

args = parser.parse_args()

try:
    download(args.local_file, args.remote_path,
             check_space=True, raise_error=True)
except Exception as e:
    print(e)
    sys.exit(1)

sys.exit()
