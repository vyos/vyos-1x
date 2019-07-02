#!/usr/bin/env python3

import sys
import os

modules = {
  "intel": ["e1000", "e1000e", "igb", "ixgb", "ixgbe", "ixgbevf", "i40e", "i40evf"],
  "accel_ppp": ["ipoe"],
  "misc": ["wireguard"]
}

if __name__ == '__main__':
    success = True

    print("[load modules] Test execution started")
    for msk in modules:
        ms = modules[msk]
        for m in ms:
            # We want to uncover all modules that fail,
            # not fail at the first one
            try:
                os.system("modprobe {0}".format(m))
            except Exception as e:
                print("[load modules] Test [modprobe {0}] failed: {1}".format(module, e))
                success = False

    if not success:
        print("Test [load modules] failed")
        sys.exit(1)
    else:
        print("[load modules] Test succeeded")
