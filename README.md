# Network Based Configuration

## Introduction

Linux provides us with a mechanism to run commands when network
interfaces are brought up and down:

man page: [/etc/network/interfaces (5)](https://manpages.org/etc-network-interfaces/5)

There are hooks for running scripts before and after interfaces are
brought up and/or taken down:

- `pre-up`: before the interface is brought up
- `up`
- `post-up`: after the interface is brought up
- `pre-down`: before the interface is taken down
- `down`
- `post-down`: after the interface is taken down

These are all nifty and good, but there's a certain lack of
configurability.  For example, we can run a command when we plug in
a network cable into a certain port, but that's kinda the extent of it.

This tool goes a little further by examining the state of the network
and allowing commands to run in certain states.  For example, if I'm
on my home network, I want to be mount a few remote filesystems; when
I'm away, it should start up the VPN, etc..

## Configuring Networks

Networks are configured with YAML files that are located in a directory
named `networks`.  Specifically, it looks for `./networks/*.yml`
(although that is configurable).

```YAML
---
# nice to have, but optional
name: "friendly name of the network"

# if true, all of the tests must pass for this configuration to match
# if false, only one test must pass for this configuration to match
require_all_matches: true

# if the external (Internet-facing) IP address of this network falls in
# this range, then this test passes.  It supports CIDR notation or just
# a single IP address.  This may be less reliable than other methods if
# the external IP address is dynamic.
external_ip_address: "1.2.3.4/29"

# this is the internal MAC address for the default gateway.  This may
# be less reliable depending on how the network is configured (e.g.,
# subnets, access points, routers, etc.) as compared to other methods.
# If the gateway is pretty static, this may work reasonably well.
gateway_mac_address: "12:34:56:78:90:ab"

# this is probably one of the less-useful tests -- the internal IP
# address of the default gateway.
gateway_ip_address: "192.168.0.1"

# these are commands that are to be run when this configuration matches
# the current network state.  They're not actually run at all -- they're
# written to STDOUT so that they can be examined, filtered, run through
# post-processing (I'm looking at you, `sed` and  `envsubst`).  It can
# be a single command or a list of commands (i.e., a YAML array).
connect_commands:
  - "echo 'hello world' > /tmp/network_based_config.txt"
```

## Configuring the tool

The tool uses environment variables to configure its core functionality:

- `CONFIG_FILE_PATTERN`: path/glob to the network configuration files;
  defaults to `./networks/*.yml`

### Configuration with .env

The tool also supports reading environment variables from `.env` files.

```env
CONFIG_FILE_PATTERN="./nteworks/*.yml"
```


## TODO

- network weight
  - only apply configurations for the highest weight

- external hostname (i.e., `nslookup` on the external IP address)
