#!/bin/bash
# Converts Global UM Wind file to netcdf
# Trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR

# START MESSAGE
cylc task-started

# Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
SERVICE="globalnwp_conv_wind"

PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d%T%Z`; $msgout Started"
echo "$MSG"
$NAGIOS $SERVICE OK $MSG

# convert 10mwind
gunzip -c /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/output/*_${CYCLE_TIME}_10mwind.gz \
    > sls_${CYCLE_TIME}_10mwind
/$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/um2netcdf -f -t -i -g /$SYSTEM/ecoconnect/wave_$SYSTEM/control/globalwave_120/attribute_sls_global.txt \
    -o sls_ \
    -p _global_sfcwind \
    sls_${CYCLE_TIME}_10mwind
CC=$?
if ((CC!=0)); then
    MSG="$msgout um2netcdf of 10mwind failed"
    echo "`date -u +%Y%m%d%T%Z`; $MSG"
    $NAGIOS $SERVICE CRITICAL $MSG
    cylc task-message -p CRITICAL "$MSG"
    cylc task-failed
    exit 1
fi
rm sls_${CYCLE_TIME}_10mwind

# Copy wind file to nwp_${SYSTEM} and tell the controller that it is ready for visualisation
cp sls_${CYCLE_TIME}_utc_global_sfcwind.nc /${SYSTEM}/ecoconnect/wave_${SYSTEM}/input/globalwave_120/.
mv sls_${CYCLE_TIME}_utc_global_sfcwind.nc /${SYSTEM}/ecoconnect/nwp_${SYSTEM}/output/global/.

cylc task-message "SLS GLOBAL WIND file for ${CYCLE_TIME} ready"

cylc task-finished
echo "`date -u +%Y%m%d%T%Z`; $msgout Finished"
exit 0
