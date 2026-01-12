#!/usr/bin/env python3
###############################################################################
# @file network_based_config.py
# @brief Emit connection commands based on the current network "identity".
#
# @details
# This module is a small decision engine that:
#   1. Loads one or more YAML configuration files describing "networks"
#      (home, office, coffee shop, VPN, etc.).
#   2. Detects the current network state using a few observable signals:
#        - External (public) IP address
#        - Default gateway IP address
#        - Default gateway MAC address
#   3. Selects configuration entries whose match criteria evaluate True
#      (or "not explicitly False", depending on policy).
#   4. Prints the configured connect commands to STDOUT.
#
# Safety posture:
#   - This script intentionally does NOT execute commands.
#     It only prints them so a caller can inspect, log, pipe, or gate execution.
#
# Configuration:
#   - CONFIG_FILE_PATTERN (environment variable)
#       A glob that selects YAML network definition files.
#       Default: "networks/*.yml"
#       Typical usage: CONFIG_FILE_PATTERN="./networks/*.yml"
#
# YAML schema (per config file; keys are optional unless stated):
#   - name (string; optional)
#       A human-readable label used only for comment output.
#   - require_all_matches (bool; optional; default True)
#       When True, all configured match tests must not be explicitly False.
#       When False, at least one configured test must be explicitly True.
#   - external_ip_address (string CIDR; optional)
#       Example: "203.0.113.0/24"
#   - gateway_ip_address (string IP; optional)
#       Example: "192.168.1.1"
#   - gateway_mac_address (string MAC; optional)
#       Example: "aa:bb:cc:dd:ee:ff"
#   - connect_commands (string or list[string]; optional)
#       The command(s) to print when the network matches.
#
# Failure modes and expectations:
#   - YAML parsing failures are printed and the corresponding file may be absent
#     from the final config set.
#   - Missing match keys are treated as "no opinion" (None) in match functions.
#     The match_* policies decide how None impacts the outcome.
###############################################################################

"""produce a series of commands based on the current network state

@brief Print (do not execute) network-specific connection commands.

@details
This file is intentionally small and procedural because its core value is
operational clarity:
- detect "where we are" on a network,
- decide which network definition matches,
- print the relevant connect commands.

The output is designed to be easy to:
- read as a human,
- pipe into other tools,
- and log during troubleshooting.

@par Non-goals
- This script does not execute commands.
- This script does not attempt to merge multiple matching configs; it prints
  commands for each config that matches.

@par Examples
@code
# Print connect commands for the current network using the default config glob:
./network_based_config.py

# Use a custom config location:
CONFIG_FILE_PATTERN="./networks/*.yml" ./network_based_config.py

# Pipe the result into a shell for execution (caller-controlled and reviewable):
./network_based_config.py | bash
@endcode
"""

import glob
import os

import ipcalc
from dotenv import load_dotenv
from yaml import YAMLError, safe_load

from lib.default_gateway import gateway_ip, gateway_mac
from lib.external_ip_address import external_ip
from lib.normalize_mac import normalize_mac


def matches_ip_address(item, key, test_ip_address):
    """Compare a configuration value against a computed IP address.

    @brief Evaluate an IP-based match predicate for a config item.

    @details
    Many network identifiers are naturally expressed as an IP or CIDR:
    - External (public) IP ranges (CIDR) can distinguish "home ISP" vs. "away".
    - Gateway IP can distinguish common private networks (e.g., 192.168.1.1).

    The config value is interpreted via ipcalc.Network(...), which supports CIDR
    notation.  The test IP address is considered a member of that network.

    @param item
        Parsed YAML mapping (dict-like) representing a single network definition.

    @param key
        The YAML key to check (e.g., "external_ip_address" or "gateway_ip_address").

    @param test_ip_address
        The detected IP address to test for membership.

    @retval bool | None
        - True if the key exists and the test IP is within the configured network.
        - False if the key exists and the test IP is not within the configured network.
        - None if the key is not present in the config (meaning: "no opinion").
    """
    if key in item:
        return test_ip_address in ipcalc.Network(item[key])

    return None


def matches_mac_address(item, key, test_mac_address):
    """Compare a configuration MAC address against a computed MAC address.

    @brief Evaluate a MAC-based match predicate for a config item.

    @details
    Gateway MAC addresses are often stable within a given environment and can be
    a strong signal when IP-based identifiers may change (e.g., DHCP churn).

    MAC addresses are normalized before comparison to reduce false mismatches
    due to formatting differences (case, delimiters, etc.).

    @param item
        Parsed YAML mapping representing a single network definition.

    @param key
        The YAML key to check (e.g., "gateway_mac_address").

    @param test_mac_address
        The detected MAC address to compare.

    @retval bool | None
        - True if the key exists and normalized MACs match.
        - False if the key exists and normalized MACs differ.
        - None if the key is not present in the config (meaning: "no opinion").
    """
    if key in item:
        normalized_test_mac_address = normalize_mac(test_mac_address)
        normalized_config_mac_address = normalize_mac(item[key])

        return normalized_test_mac_address == normalized_config_mac_address

    return None


def matches_external_ip_address(item):
    """Determine whether the external/public IP matches this config item.

    @brief Match on external IP (public internet address).

    @details
    This is commonly used to detect a home ISP range or a known office NAT range.
    The underlying implementation obtains the current external IP via external_ip().

    YAML key: external_ip_address (CIDR)

    @param item
        Parsed YAML network definition.

    @retval bool | None
        See matches_ip_address().
    """
    return matches_ip_address(item, "external_ip_address", external_ip())


def matches_gateway_ip_address(item):
    """Determine whether the default gateway IP matches this config item.

    @brief Match on the default gateway's IP address.

    @details
    This is a quick discriminator for many private networks (e.g., 192.168.0.1 vs 10.0.0.1),
    though it is not globally unique and may collide across environments.

    YAML key: gateway_ip_address (IP or CIDR-like value accepted by ipcalc.Network)

    @param item
        Parsed YAML network definition.

    @retval bool | None
        See matches_ip_address().
    """
    return matches_ip_address(item, "gateway_ip_address", gateway_ip())


def matches_gateway_mac_address(item):
    """Determine whether the default gateway MAC matches this config item.

    @brief Match on the default gateway's MAC address.

    @details
    The gateway MAC address is often the most stable identifier for a network,
    particularly when IP ranges overlap (e.g., multiple locations using 192.168.1.0/24).

    YAML key: gateway_mac_address (MAC)

    @param item
        Parsed YAML network definition.

    @retval bool | None
        See matches_mac_address().
    """
    return matches_mac_address(item, "gateway_mac_address", gateway_mac())


def read_config_files(file_pattern):
    """Load YAML config files selected by a glob pattern.

    @brief Read and parse network definition files.

    @details
    The CONFIG_FILE_PATTERN environment variable controls which YAML files are
    loaded.  The pattern is expanded using glob.glob().

    Failure handling:
    - YAML parsing failures are printed to STDOUT (via print(exc)).
    - Successfully parsed files are returned in a dict keyed by filename.

    @param file_pattern
        Glob pattern (string) used to locate YAML files.

    @retval dict
        Mapping of filename -> parsed YAML content (dict-like).
    """
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
    """Decide whether a single network definition matches current state.

    @brief Apply the configured match policy for this item.

    @details
    This function is the policy switch for how multiple match tests are combined.

    YAML key: require_all_matches (bool; default True)

    Semantics:
    - When require_all_matches is True:
        The config matches if none of the evaluated tests are explicitly False.
        (Missing keys return None and are treated as "no opinion" rather than failure.)
    - When require_all_matches is False:
        The config matches if at least one evaluated test is explicitly True.
        (Missing keys return None and do not contribute to a match.)

    @param item
        Parsed YAML network definition.

    @retval bool
        True if the item matches under the selected policy, otherwise False.
    """

    require_all_matches = True

    if "require_all_matches" in item:
        require_all_matches = item["require_all_matches"]

    if require_all_matches:
        return match_all(item)

    return match_one(item)


def match_all(item):
    """Match policy: all configured tests must not explicitly fail.

    @brief Return True when all match predicates are not False.

    @details
    This is intentionally lenient with missing match keys:
    - A missing key yields None from the underlying match function.
    - None is treated as "not explicitly False" and therefore does not fail the match.

    This makes it possible to define a network using only one or two signals
    while still using the "all" policy.

    @param item
        Parsed YAML network definition.

    @retval bool
        True if no match predicate returned False; otherwise False.
    """
    return (
        (matches_external_ip_address(item) is not False)
        and (matches_gateway_ip_address(item) is not False)
        and (matches_gateway_mac_address(item) is not False)
    )


def match_one(item):
    """Match policy: at least one configured test must succeed.

    @brief Return True when any match predicate is explicitly True.

    @details
    This is intentionally strict with missing match keys:
    - A missing key yields None from the underlying match function.
    - None is not True and therefore does not contribute to a match.

    This policy is useful when multiple weak signals are present and any one of
    them should be sufficient to identify the network.

    @param item
        Parsed YAML network definition.

    @retval bool
        True if at least one predicate returned True; otherwise False.
    """
    return (
        (matches_external_ip_address(item) is True)
        or (matches_gateway_ip_address(item) is True)
        or (matches_gateway_mac_address(item) is True)
    )


def list_commands(item):
    """Render the connect commands for a matching network definition.

    @brief Build the STDOUT payload for a matching config item.

    @details
    Output format:
    - A leading comment line identifying the section as "connect commands".
    - If "name" is present, it is included for human readability.
    - If connect_commands is missing, only the header is returned.

    YAML keys:
    - name (optional)
    - connect_commands (optional; string or list[string])

    Safety:
    - This function returns text.  It does not execute anything.

    @param item
        Parsed YAML network definition.

    @retval str
        The rendered command text (including a header comment).
    """

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

    # Load environment variables from a local .env file when present.
    # This supports keeping per-machine configuration (like CONFIG_FILE_PATTERN)
    # out of shell history and out of committed source code.
    load_dotenv()

    # CONFIG_FILE_PATTERN controls which YAML network definitions are loaded.
    # The default assumes execution from the repository root.
    config_file_pattern = os.getenv("CONFIG_FILE_PATTERN", "networks/*.yml")

    all_config_data = read_config_files(config_file_pattern)

    # Evaluate each network definition independently.
    # If multiple definitions match, commands are printed for each match.
    for filename, value in all_config_data.items():
        if matches_configuration(value):
            print(list_commands(value))
