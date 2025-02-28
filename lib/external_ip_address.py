#!/usr/bin/env python3

"""acquire the external IP address for this network"""

from requests import get


def external_ip():
    """get the external IP address for this network"""
    return get("https://api.ipify.org", timeout=10).content.decode("utf8")


if __name__ == "__main__":
    print(f"My public IP address is: {format(external_ip())}")
