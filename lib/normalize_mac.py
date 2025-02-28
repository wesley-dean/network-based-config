#!/usr/bin/env python3
"""given a MAC address, normalize it"""

import sys


def normalize_mac(mac):
    """iterates through chunks of a MAC address to normalize it"""
    parts = [int(x, 16) for x in mac.split(":")]
    return ":".join(f"{part:02x}" for part in parts)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "-h" or sys.argv[1] == "--help":
        print("usage: normalize_mac 12:34:56:78:89:0a")
    else:
        print(normalize_mac(sys.argv[1]))
