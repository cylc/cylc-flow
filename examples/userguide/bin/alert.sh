#!/bin/bash

ALERT=$1
shift
NAME=$1
shift
CTIME=$1
shift
MESSAGE=$@

if [[ $ALERT != '--submitted' ]] && \
    [[ $ALERT != '--started' ]] && \
    [[ $ALERT != '--finished' ]] && \
    [[ $ALERT != '--failed' ]] && \
    [[ $ALERT != '--submit-failed' ]]; then
    echo "alert.sh ERROR, unknown alert type: $ALERT" >&2
    exit 1
fi

ALERT=${ALERT#--}

echo "!! TASK ALERT: $NAME $ALERT for $CTIME"
if [[ $ALERT = failed ]] || [[ $ALERT = submit-failed ]]; then
    echo "!! Message: $MESSAGE"
fi
