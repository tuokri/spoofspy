#!/usr/bin/env bash

set -x

export OVERMIND_PROCFILE=Procfile-jobs
export OVERMIND_ANY_CAN_DIE=1
export OVERMIND_AUTO_RESTART=beat,worker1,worker2,a2s_worker1,a2s_worker2,a2s_worker3

overmind start
