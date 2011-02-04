#!/bin/bash
# Temporary script for testing end to end.
# Verify if NZLAM data files are available on Pa.
# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR
# START MESSAGE
cylc message --started
# Check the number of arguments
if [ "$#" -ne 1 ]; then
        # FATAL ERROR
	MSG="There needs to be 1 argument present."
        cylc message -p CRITICAL $MSG 
        cylc message --failed
        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} $MSG"
        exit 1
fi
# Set parameters
SOURCE=$1
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
			cylc message -p CRITICAL "ssh to $SOURCE not working"
			cylc message --failed
		        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} ssh failure to $SOURCE $result"
			exit 1
		fi
	else
		break
	fi
done
# Run loop until file is found
FILEPA="'process_nzlam_output.*finished for $CYCLE_TIME'"
echo "FILEPA: $FILEPA"
echo "SOURCE: $SOURCE"
while true; do
	if ! result=$(ssh $SOURCE "grep -s $FILEPA /var/log/ecoconnect*"); then
	        echo $result
        fi		
        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} $result for $filename"
        if echo "$result" | grep "finished" >/dev/null 2>&1
      	then
                echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Found NZLAM output, will send message to cylc"
                echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Source: $SOURCE, Location: /var/log/ecoconnect"
                cylc message "process_nzlam_output finished for $CYCLE_TIME"
                # SUCCESS MESSAGE
                cylc message --succeeded
                break
	fi
# Trying every minute
        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Trying again to check for $FILEPA file on $SOURCE in /var/log/ecoconnect, be back in 1 minute"
	sleep 60
done
