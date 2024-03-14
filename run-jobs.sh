#!/usr/bin/env bash

set -x

sysctl -w net.ipv4.ping_group_range='0 2147483647'
sysctl -p --system

overmind start
