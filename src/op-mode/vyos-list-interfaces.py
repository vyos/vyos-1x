#!/usr/bin/env python3

import netifaces

if __name__ == '__main__':
    interfaces = netifaces.interfaces()

    print(" ".join(interfaces))
