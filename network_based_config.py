#!/usr/bin/env python3

"""produce a series of commands based on the current network state"""


import glob
import os

import ipcalc
from dotenv import load_dotenv
from yaml import YAMLError, safe_load

from lib.default_gateway import gateway_ip, gateway_mac
from lib.external_ip_address import external_ip
from lib.normalize_mac import normalize_mac


def matches_ip_address(item, key, test_ip_address):
    """given a configuration item, compare a value with a test IP address"""
    if key in item:
        return test_ip_address in ipcalc.Network(item[key])

    return None


def matches_mac_address(item, key, test_mac_address):
    """given a configuration item, compare a value with a test MAC address"""
    if key in item:
        normalized_test_mac_address = normalize_mac(test_mac_address)
        normalized_config_mac_address = normalize_mac(item[key])

        return normalized_test_mac_address == normalized_config_mac_address

    return None


def matches_external_ip_address(item):
    """determine if the external IP address matches this config item"""
    return matches_ip_address(item, "external_ip_address", external_ip())


def matches_gateway_ip_address(item):
    """determine if the gateway's IP address matches this config item"""
    return matches_ip_address(item, "gateway_ip_address", gateway_ip())


def matches_gateway_mac_address(item):
    """determine if the gateways's MAC address matches this config item"""
    return matches_mac_address(item, "gateway_mac_address", gateway_mac())


def read_config_files(file_pattern):
    """given a path/glob, read all of the config files that match"""
    config_files = glob.glob(file_pattern)
    config_data = {}

    for config_file in config_files:
        with open(config_file, encoding="utf-8") as stream:
            try:
                config_data[config_file] = safe_load(stream)
            except YAMLError as exc:
                print(exc)
    return config_data


def matches_configuration(item):
    """returns true if this configi item matches the network's state"""

    require_all_matches = True

    if "require_all_matches" in item:
        require_all_matches = item["require_all_matches"]

    if require_all_matches:
        return match_all(item)

    return match_one(item)


def match_all(item):
    """returns true if all tests pass"""
    return (
        (matches_external_ip_address(item) is not False)
        and (matches_gateway_ip_address(item) is not False)
        and (matches_gateway_mac_address(item) is not False)
    )


def match_one(item):
    """returns true if at least one test passes"""
    return (
        (matches_external_ip_address(item) is True)
        or (matches_gateway_ip_address(item) is True)
        or (matches_gateway_mac_address(item) is True)
    )


def list_commands(item):
    """get the commands to run and return them as a string"""

    return_string = "# connect commands"

    if "name" in item:
        return_string += " for '" + item["name"] + "'"

    return_string += "\n"

    if "connect_commands" not in item:
        return return_string

    if isinstance(item["connect_commands"], str):
        return_string += item["connect_commands"]
    elif isinstance(item["connect_commands"], list):
        return_string += "\n".join(item["connect_commands"])

    return return_string


if __name__ == "__main__":

    load_dotenv()

    config_file_pattern = os.getenv("CONFIG_FILE_PATTERN", "networks/*.yml")

    all_config_data = read_config_files(config_file_pattern)

    for filename, value in all_config_data.items():
        if matches_configuration(value):
            print(list_commands(value))
