#!/bin/bash
# Verify if the streamq file is ready to be downloaded or already downloaded
# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR
# START MESSAGE
cylc message --started
# Set parameters
local_file="/test/ecoconnect/data_test/output/td2cf/streamq_${CYCLE_TIME}_utc_ods_nz.nc"
source="ecoconnect_oper@pa"
file="/oper/data_oper/output/td2cf/streamq_${CYCLE_TIME}_utc_ods_nz.nc"
# Check if file is aready lcoally available
test -f $local_file && result="File streamq exists locally" || result="File streamq does not exist locally"
echo "${CYCLE_TIME}: $result"
if [ "$result" = "File streamq exists locally" ]
then
        echo "${CYCLE_TIME}: File streamq exist locally, will download again anyway"
	cylc message "file streamq_${CYCLE_TIME}_utc_ods_nz.nc available for download"
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
	ssh $source test -f $file && result="File streamq exists on pa" || result="File streamq does not exsits on pa"
	echo "${CYCLE_TIME}: $result"
	if [ "$result" = "File streamq exists on pa" ]
	then
		echo "${CYCLE_TIME}: Found streamq file, will start the download"
		cylc message "file streamq_${CYCLE_TIME}_utc_ods_nz.nc available for download"
		# SUCCESS MESSAGE
		cylc message --succeeded
		break
	fi
# Trying every minute
        echo "${CYCLE_TIME}: Trying again to check for tn file, be back in 1 minute"
	sleep 60
done
