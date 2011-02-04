#!/bin/bash
# Verify if Global wind file is ready to be downloaded or already downloaded
# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR
# START MESSAGE
cylc message --started
# Set parameters
DIR="/test/ecoconnect/ecoconnect_test/output"
local_file="$DIR/output/qwgl_daily_${CYCLE_TIME}_ice.gz"
source="ecoconnect_oper@pa"
file="/oper/ecoconnect_oper/output/qwgl_daily_${CYCLE_TIME}_ice.gz"
# Check if file is aready lcoally available
test -f $local_file && result="File ice global exists locally" || result="File ice global does not exist locally"
echo "${CYCLE_TIME}: $result"
if [ "$result" = "File ice global exists locally" ]
then
        echo "${CYCLE_TIME}: File ice global exist locally, will download again anyway"
	cylc message "file qwgl_daily_${CYCLE_TIME}_icd.gz available for download"
	# SUCCESS MESSAGE
        cylc message --succeeded
        exit 0
fi
# Check if ssh is OK
ssh -q -o "BatchMode=yes" $source "echo 2>&1" && result="OK" || result="NOK"
echo "${CYCLE_TIME}: $result"
if [ "$result" = "NOK" ]
then
	# FATAL ERROR
	cylc message -p CRITICAL "ssh to pa not working"
	cylc message --failed
        echo "${CYCLE_TIME}: ssh failure $result"
	exit 1
fi

# Run loop until file is found
while true; do
	ssh $source test -f $file && result="File ice global exists on pa" || result="File ice global does not exsits on pa"
	echo "${CYCLE_TIME}: $result"
	if [ "$result" = "File ice global exists on pa" ]
	then
		echo "${CYCLE_TIME}: Found ice global file, will start the download"
		cylc message "file qwgl_daily_${CYCLE_TIME}_ice.gz available for download"
		# SUCCESS MESSAGE
		cylc message --succeeded
		break
	fi
# Trying every minute
        echo "${CYCLE_TIME}: Trying again to check for ice global file, be back in 1 minute"
	sleep 60
done
