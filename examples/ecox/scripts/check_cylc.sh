#!/bin/bash
#
# Check if Cylc is running - Send a NAGIOS alert if not.
#
# Author: Bernard Miville
# Date: 15 September 2010
#
set -e

SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
PROG=`basename $0`
SERVICE="check_cylc"
msgout="SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"
up=":cylc.ecoconnect_oper.ecoconnect is running"
NAGIOS="echo"
check_err="OK"
check_status_err="OK"

# Infinite Loop
while [ 1 ]
do
    MSG="`date -u +%Y%m%d" "%T" "%Z`"
    # cylc command does not exist
    if ! cylc_status=$(cylc ping ecoconnect); then
        if [ "$check_status_err" != "Error" ]; then
            # Send a CRITICAL alert once
            msgout="$MSG; SCRIPT:${PROG}; $cylc_status"
            $NAGIOS $SERVICE CRITICAL $msgout "(cylc command not found)"
            check_status_err="Error"
        fi
    elif [ "$check_status_err" = "Error" ]; then
        msgout="$MSG; SCRIPT:${PROG}; $cylc_status"
        # Send a recovery alert once
        $NAGIOS $SERVICE OK $msgout
        check_status_err="OK"
    fi
    # ecoconnect suite is not running
    msgout="$MSG; SCRIPT:${PROG}; $cylc_status"
    if ! check_cylc=$(cylc ping ecoconnect | grep "$up"); then
        if [ "$check_err" != "Error" ]; then
            # Send a CRITICAL alert once
            $NAGIOS $SERVICE CRITICAL $msgout "(ecoconnect suite is not running)"
            check_err="Error"
        fi
    elif [ "$check_err" != "OK" ]; then
        # Send a recovery alert once
        $NAGIOS $SERVICE OK $msgout
        check_err="OK"
    fi
    sleep 5
done
