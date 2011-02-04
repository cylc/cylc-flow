#!/bin/bash
# Verify if NZLAM met files are ready to be downloaded or already downloaded
# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR
# START MESSAGE
cylc message --started
# Set parameters
DIR="/test/ecoconnect/nwp_test"
local_file_000="$DIR/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_000.nc"
local_file_012="$DIR/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_012.nc"
local_file_024="$DIR/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_024.nc"
local_file_036="$DIR/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_036.nc"
local_file_048="$DIR/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_048.nc"
source="ecoconnect_oper@pa"
file_000="/oper/nwp_oper/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_000.nc"
file_012="/oper/nwp_oper/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_012.nc"
file_024="/oper/nwp_oper/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_024.nc"
file_036="/oper/nwp_oper/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_036.nc"
file_048="/oper/nwp_oper/output/nzlam_12/met_${CYCLE_TIME}_utc_nzlam_12_048.nc"
# Check if files are already locally available
test -f $local_file_000 && result_000="File met exists locally" || result_000="File met does not exist locally"
test -f $local_file_012 && result_012="File met exists locally" || result_012="File met does not exist locally"
test -f $local_file_024 && result_024="File met exists locally" || result_024="File met does not exist locally"
test -f $local_file_036 && result_036="File met exists locally" || result_036="File met does not exist locally"
test -f $local_file_048 && result_048="File met exists locally" || result_048="File met does not exist locally"
echo "${CYCLE_TIME}: 000: $result_000"
echo "${CYCLE_TIME}: 012: $result_012"
echo "${CYCLE_TIME}: 024: $result_024"
echo "${CYCLE_TIME}: 036: $result_036"
echo "${CYCLE_TIME}: 048: $result_048"
if [ "$result_000" = "File met exists locally" -a "$result_012" = "File met exists locally" -a "$result_024" = "File met exists locally" -a "$result_036" = "File met exists locally" -a "$result_048" = "File met exists locally" ]
then
        echo "${CYCLE_TIME}: Files met exist locally, will download again anyway"
	cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_000.nc available for download"
        cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_012.nc available for download"
        cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_024.nc available for download"
        cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_036.nc available for download"
        cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_048.nc available for download"
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

# Run loop until all met files are found
while true; do
	ssh $source test -f $file_000 && result_000="File met exists on pa" || result_000="File met does not exsits on pa"
        ssh $source test -f $file_012 && result_012="File met exists on pa" || result_012="File met does not exsits on pa"
        ssh $source test -f $file_024 && result_024="File met exists on pa" || result_024="File met does not exsits on pa"
        ssh $source test -f $file_036 && result_036="File met exists on pa" || result_036="File met does not exsits on pa"
        ssh $source test -f $file_048 && result_048="File met exists on pa" || result_048="File met does not exsits on pa"
	echo "${CYCLE_TIME}: 000: $result_000"
        echo "${CYCLE_TIME}: 012: $result_012"
        echo "${CYCLE_TIME}: 024: $result_024"
        echo "${CYCLE_TIME}: 036: $result_036"
        echo "${CYCLE_TIME}: 048: $result_048"
	if [ "$result_000" = "File met exists on pa" -a "$result_012" = "File met exists on pa" -a "$result_024" = "File met exists on pa" -a "$result_036" = "File met exists on pa" -a "$result_048" = "File met exists on pa" ]
	then
		echo "${CYCLE_TIME}: Found met files, will start the download"
		cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_000.nc available for download"
                cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_012.nc available for download"
                cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_024.nc available for download"
                cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_036.nc available for download"
                cylc message "file met_${CYCLE_TIME}_utc_nzlam_12_048.nc available for download"
		# SUCCESS MESSAGE
		cylc message --succeeded
		break
	fi
# Trying every minute
        echo "${CYCLE_TIME}: Trying again to check for met files, be back in 1 minute"
	sleep 60
done
