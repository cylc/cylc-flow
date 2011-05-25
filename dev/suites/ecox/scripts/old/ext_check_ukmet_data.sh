#!/bin/bash
# Verify if UK MetOffice data files are available.
# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR
# START MESSAGE
cylc message --started
# Check the number of arguments
if [ "$#" -ne 3 ]; then
        # FATAL ERROR
	MSG="There needs to be 3 arguments present."
        cylc message -p CRITICAL $MSG 
        cylc message --failed
        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} $MSG"
        exit 1
fi
# Set parameters
SOURCE=$1
DIR=$2
FILEUKMET=$3
REF_TIME=$CYCLE_TIME
file="$DIR/$FILEUKMET"
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
while true; do
	ssh $SOURCE test -f $file && result="File $FILEUKMET exists on $SOURCE" || result="File $FILEUKMET does not exsits on $SOURCE"
	echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} $result in $file"
	if [ "$result" = "File $FILEUKMET exists on $SOURCE" ]
	then
		echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Found ukmet file $FILEUKMET, will send message to cylc"
                echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Source: $SOURCE, Location: $file"
		cylc message "file $FILEUKMET ready"
		# SUCCESS MESSAGE
		cylc message --succeeded
		break
	fi
# Trying every minute
        echo "`date -u +%Y%m%d%H%M%Z` CYCLE_TIME:${REF_TIME} Trying again to check for $FILEUKMET file in $file on $SOURCE, be back in 1 minute"
	sleep 60
done
