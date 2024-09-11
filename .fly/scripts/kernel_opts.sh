#!/usr/bin/env bash
echo "setting kernel options"
sysctl -w net.ipv4.ping_group_range='0 2147483647'
