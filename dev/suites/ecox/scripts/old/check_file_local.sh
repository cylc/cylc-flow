#!/bin/bash
# Verify if a file is available locally.
# Trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR
# START MESSAGE
cylc task-started

# Main Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
n=0
PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d%T%Z`; $msgout Started"
echo "$MSG"

# Check the number of arguments
if [ "$#" -ne 5 ]; then
    # FATAL ERROR
	MSG="There needs to be 5 arguments present."
    cylc task-message -p CRITICAL $MSG 
    cylc task-failed
    echo "`date -u +%Y%m%d%S%Z` $msgout $MSG"
    exit 1
fi

# Set other parameters
FILE_DIR=$1
FILE_NAME=$2
SERVICE=$3
TIMEOUT=$4
CYLC_MESSAGE=$5
$NAGIOS $SERVICE OK $MSG
FILE_LOC="$FILE_DIR/$FILE_NAME"
REF_TIME=$CYCLE_TIME
# Run loop until file is found
while true; do
   if [ `ls $FILE_LOC` ]; then
        echo "`date -u +%Y%m%d%T%Z` $msgout Found file $FILE_NAME in $FILE_DIR, will send message to cylc"
        # Make sure is finished being copied over or downloaded 
		while true; do
			if [ ! `fuser $FILE_LOC | wc -c` -eq 0 ]; then
				echo "`date -u +%Y%m%d%T%Z` $msgout File $FILE_NAME not finished being copied"
				sleep 30
			else
				echo "`date -u +%Y%m%d%T%Z` $msgout File $FILE_NAME now fully copied"
				break		
			fi
		done
                cylc task-message $CYLC_MESSAGE
                # SUCCESS MESSAGE
                cylc task-finished
                exit 0
	fi
# Trying every minute
        n=$((n+1))
        echo "`date -u +%Y%m%d%T%Z`; $msgout Trying again (n=$n) to check for $FILE_NAME file in $FILE_DIR, be back in 1 minute"
        # Send Cylc and NAGIOS a critical message if file not found
        # after $TIMEOUT 
        if [ $n = $TIMEOUT ]; then
            MSG="$msgout $FILE_NAME in $FILE_DIR has not been found yet in the past $TIMEOUT minutes."
            echo "`date -u +%Y%m%d%T%Z`; $MSG"
            # Send critical message but continue looking.
            cylc task-message -p CRITICAL $MSG
            $NAGIOS $SERVICE CRITICAL $MSG
        fi
	sleep 60
done
