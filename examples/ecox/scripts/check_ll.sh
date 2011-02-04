#!/bin/bash
#
# Check if loadleveler is running - Send a NAGIOS alert if not.
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
up="fc-test.*.Avail"
NAGIOS="echo"
check_err="OK"
check_status_err="OK"

# Infinite Loop
while [ 1 ]
do
    MSG="`date -u +%Y%m%d" "%T" "%Z`"
    # llstatus command does not exist
    if ! ll_status=$(llstatus); then
        if [ "$check_status_err" != "Error" ]; then
            # Send a CRITICAL alert once
            msgout="$MSG; SCRIPT:${PROG}; (llstatus command return an error)"
            $NAGIOS $SERVICE CRITICAL $msgout
            check_status_err="Error"
        fi
    elif [ "$check_status_err" = "Error" ]; then
        msgout="$MSG; SCRIPT:${PROG}; (loadleveler is running)"
        # Send a recovery alert once
        $NAGIOS $SERVICE OK $msgout
        check_status_err="OK"
    fi
    # loadleveler is not running
    msgout="$MSG; SCRIPT:${PROG}; (loadleveler is not running)"
    if ! check_ll=$(llstatus | grep "$up"); then
        if [ "$check_err" != "Error" ]; then
            # Send a CRITICAL alert once
            $NAGIOS $SERVICE CRITICAL $msgout
            check_err="Error"
        fi
    elif [ "$check_err" != "OK" ]; then
        # Send a recovery alert once
        msgout="$MSG; SCRIPT:${PROG}; (loadleveler is running)"
        $NAGIOS $SERVICE OK $msgout
        check_err="OK"
    fi
#    sleep 5
done
