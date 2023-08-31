#!/usr/bin/env bash

set -x

export OVERMIND_PROCFILE=Procfile-jobs
export OVERMIND_CAN_DIE=beat,worker,a2s_worker
export OVERMIND_AUTO_RESTART=beat,worker,a2s_worker

overmind start
