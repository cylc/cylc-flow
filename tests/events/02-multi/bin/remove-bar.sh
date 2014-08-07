#!/bin/bash

SUITE=$2

# wait for task bar to fail
cylc suite-state $SUITE --task=bar --cycle=1 \
    --status=failed --max-polls=10 --interval=2

# then remove it
cylc remove $SUITE bar 1
