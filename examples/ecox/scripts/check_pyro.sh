#!/bin/bash
#
# Check if Pyro is running - Send a NAGIOS alert if not.
#
# Author: Bernard Miville
# Date: 15 September 2010
#
set -e

SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
PROG=`basename $0`
SERVICE="check_pyro"
msgout="SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"
up="NS is up and running!"
check_err="OK"
check_status_err="OK"

NAGIOS="echo"
# Infinite Loop
while [ 1 ]
do
    MSG="`date -u +%Y%m%d" "%T" "%Z`"
    # pyro command does not exist
    if ! pyro_status=$(pyro-nsc ping); then
        if [ "$check_status_err" != "Error" ]; then
            # Send a CRITICAL alert once
            msgout="$MSG; SCRIPT:${PROG}; $pyro_status"
            $NAGIOS $SERVICE CRITICAL $msgout "(pyro-nsc command not found)"
            check_status_err="Error"
        fi
    elif [ "$check_status_err" = "Error" ]; then
        msgout="$MSG; SCRIPT:${PROG}; $pyro_status"
        # Send a recovery alert once
        $NAGIOS $SERVICE OK $msgout
        check_status_err="OK"
    fi
    # pyro name server is down
    msgout="$MSG; SCRIPT:${PROG}; $pyro_status"
    if ! check_pyro=$(pyro-nsc ping | grep "$up"); then
        if [ "$check_err" != "Error" ]; then
            # Send a CRITICAL alert once
            $NAGIOS $SERVICE CRITICAL $msgout "(pyro name server not running)"
            check_err="Error"
        fi
    elif [ "$check_err" != "OK" ]; then
        # Send a recovery alert once
        $NAGIOS $SERVICE OK $msgout
        check_err="OK"
    fi
    sleep 5
done
