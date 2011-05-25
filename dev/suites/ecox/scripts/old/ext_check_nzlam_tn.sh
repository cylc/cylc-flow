#!/bin/bash
# Verify if NZLAM tn file is ready to be downloaded or already downloaded
# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR
# START MESSAGE
cylc message --started
# Set parameters
DIR="/test/ecoconnect/nwp_test"
local_file="$DIR/output/nzlam_12/tn_${CYCLE_TIME}_utc_nzlam_12.nc"
source="ecoconnect_oper@pa"
file="/oper/nwp_oper/output/nzlam_12/tn_${CYCLE_TIME}_utc_nzlam_12.nc"
# Check if file is aready lcoally available
test -f $local_file && result="File tn exists locally" || result="File tn does not exist locally"
echo "${CYCLE_TIME}: $result"
if [ "$result" = "File tn exists locally" ]
then
        echo "${CYCLE_TIME}: File tn exist locally, will download again anyway"
	cylc message "file tn_${CYCLE_TIME}_utc_nzlam_12.nc available for download"
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
	ssh $source test -f $file && result="File tn exists on pa" || result="File tn does not exsits on pa"
	echo "${CYCLE_TIME}: $result"
	if [ "$result" = "File tn exists on pa" ]
	then
		echo "${CYCLE_TIME}: Found tn file, will start the download"
		cylc message "file tn_${CYCLE_TIME}_utc_nzlam_12.nc available for download"
		# SUCCESS MESSAGE
		cylc message --succeeded
		break
	fi
# Trying every minute
        echo "${CYCLE_TIME}: Trying again to check for tn file, be back in 1 minute"
	sleep 60
done
