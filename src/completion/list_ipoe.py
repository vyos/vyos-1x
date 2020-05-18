#!/usr/bin/env python3

import argparse
from vyos.command import popen

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selector', help='Selector: username|ifname|sid', required=True)
    args = parser.parse_args()

    output, err = popen("accel-cmd -p 2002 show sessions {0}".format(args.selector))
    if not err:
        res = output.split("\r\n")
        # Delete header from list
        del res[:2]
        print(' '.join(res))
