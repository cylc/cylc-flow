#!/bin/bash
# Temporary script for testing end to end.
# Verify if UK MetOffice data files are available on Pa.
# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR
# START MESSAGE
cylc mesk-started
# Check the number of arguments
if [ "$#" -ne 2 ]; then
        # FATAL ERROR
	MSG="There needs to be 2 arguments present."
        cylc task-message -p CRITICAL $MSG 
        cylc task-failed
        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} $MSG"
        exit 1
fi
# Set parameters
SOURCE=$1
filename=$2
REF_TIME=$CYCLE_TIME
# First check if ssh is OK (check 5 times before failing)
for a in {1..5}
do
	ssh -q -o "BatchMode=yes" $SOURCE "echo 2>&1" && result="OK" || result="NOK"
	echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} $result"
	if [ "$result" = "NOK" ]
	then
		if [ $a = 5 ]; then 
			# FATAL ERROR
			cylc task-message -p CRITICAL "ssh to $SOURCE not working"
			cylc task-failed
		        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} ssh failure to $SOURCE $result"
			exit 1
		fi
	else
		break
	fi
done
# Run loop until file is found
FILEPA="'Got .*$filename'"
echo "FILEPA: $FILEPA"
echo "SOURCE: $SOURCE"
while true; do
	if ! result=$(ssh $SOURCE "grep -s $FILEPA /var/log/ecoconnect*"); then
	        echo $result
        fi		
        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} $result for $filename"
        if echo "$result" | grep "Got" >/dev/null 2>&1
      	then
                echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Found ukmet file $filename, will send message to cylc"
                echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Source: $SOURCE, Location: /var/log/ecoconnect"
                cylc task-message "file $filename available for download"
                # SUCCESS MESSAGE
                cylc task-finished
                break
	fi
# Trying every minute
        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Trying again to check for $filename file on $SOURCE in /var/log/ecoconnect, be back in 1 minute"
	sleep 60
done
