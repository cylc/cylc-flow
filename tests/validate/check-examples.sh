#!/bin/bash

set -e
for SDEF in $( find $CYLC_DIR/examples -name suite.rc ); do
    if ! cylc val --no-write $SDEF; then
        echo "VALIDATION ERROR: $SDEF" >&2
        exit 1
    fi
done

