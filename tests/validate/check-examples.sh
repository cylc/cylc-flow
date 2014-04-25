#!/bin/bash

declare -A BAD

for SDEF in $( find $CYLC_DIR/examples -name suite.rc ); do
    # capture validation stderr:
    RES=$( cylc val --no-write --debug $SDEF 2>&1 >/dev/null )
    # store it, if any, keyed by suite dir:  
    [[ -n $RES ]] && BAD[$SDEF]=$RES
done

NBAD=${#BAD[@]}
if (( NBAD == 0 )); then
    echo "All suites validate OK"
else
    echo "ERROR: $NBAD suites failed validation" >&2
    for DIR in ${!BAD[@]}; do
        echo "" >&2
        echo "${DIR}:" >&2
        echo "   ${BAD[$DIR]}" >&2
    done
    exit 1
fi

