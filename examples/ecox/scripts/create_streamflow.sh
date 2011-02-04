#!/bin/bash
#
# Create streamflow file on Tideda server
#
# Author: Bernard Miville
# Date: 5 August 2010
#
# Trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR

# START MESSAGE
cylc task-started

# Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
SERVICE="ext_create_streamflow"

source="tdserver2008.niwa.co.nz"
port="58004"
success=0
year=${CYCLE_TIME:0:4}
month=${CYCLE_TIME:4:2}
day=${CYCLE_TIME:6:2}
hour=${CYCLE_TIME:8:2}
date="\"/REF=$year-$month-$day $hour:00:00\""
PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"

$NAGIOS $SERVICE OK $MSG

# Possible responses
CMDRUN="100 COMMAND RUNNING"
CMDQUE="100 COMMAND QUEUED"
CMDCOM="100 COMMAND COMPLETE"
CMDFAI="100 COMMAND FAILED with exitcode=2"
CMDTIM="100 COMMAND TIMEOUT"
CMDSRV="100 Tideda TCP Server"

cmd="command MakeStreamobs.bat $date"

echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Command: $cmd"

# Connect to server: try 5 times
for a in {1..5}; do
     if ! exec 3<>/dev/tcp/$source/$port; then 
       MSG="$msgout Attempt number $a, Connection failed to $source:$port"
       echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
       cylc message -p WARNING $MSG
       # wait 5 seconds before trying again
       sleep 5
    else
       echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Connection successful to $source:$port"
       success=1
       break;
    fi
done

if [ $success -eq 0 ]; then
    MSG="$msgout Connection failed $a times to $source:$port"
    echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
    $NAGIOS $SERVICE CRITICAL $MSG
    cylc task-message -p CRITICAL $MSG 
    cylc task-failed
    exit 1
fi

# Send commands
echo "$cmd" 1>&3
echo "quit" 1>&3

# Check reply from server if command running and complete
while read 0<&3
do
    # Remove control characters from response
    response=`echo $REPLY | tr -d '\n\r'`
    echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Response: $response"
    # Check response
    case $response in
        $CMDRUN*) 
            echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Streamflow command running" 
            ;;
        $CMDQUE*) 
            echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Streamflow command in the queue" 
            ;;
        $CMDCOM*) 
            MSG="$msgout Streamflow command completed"
            echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
            # Close connection
            exec 3>&-
            cylc task-message "STREAMOBS file available for download for ${CYCLE_TIME}"
            cylc task-finished 
            exit 0
            ;;
        $CMDFAI*) 
            MSG="$msgout Streamflow command failed"
            echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
            # Close connection
            exec 3>&-
            cylc task-message -p CRITICAL $MSG
            cylc task-failed
            exit 1
            ;;
        $CMDTIM*) 
            MSG="$msgout Streamflow command timed out"
            echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
            # Close connection
            exec 3>&-
            cylc task-message -p CRITICAL $MSG
            cylc task-failed
            exit 1
            ;;
        $CMDSRV*) 
            echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Connected to Tideda server"
            ;;
        *) 
            MSG="$msgout Streamflow command failed"
            echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
            # Close connection
            exec 3>&-
            $NAGIOS $SERVICE CRITICAL $MSG
            cylc task-message -p CRITICAL $MSG
            cylc task-failed
            exit 1
            ;;
    esac
done
