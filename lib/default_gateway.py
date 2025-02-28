#!/usr/bin/env python3

"""utility functions for getting the default gateway's configuration"""

import getmac
import netifaces


def gateway_ip(gateway="default"):
    """return the IP address of the default gateway"""
    gateways = netifaces.gateways()
    return gateways[gateway][netifaces.AF_INET][0]


def gateway_mac(gateway="default"):
    """return the MAC address of the default gateway"""
    return getmac.get_mac_address(ip=gateway_ip(gateway))


if __name__ == "__main__":
    print(f"The IP address of my default gateway is: {format(gateway_ip())}")
    print(f"The MAC address of my default gateway is {format(gateway_mac())}")
