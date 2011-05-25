#!/bin/bash
# Converts Global UM sea ice file to netcdf
# Trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR

# START MESSAGE
cylc task-started

# 24 July 2008: the new sea ice file has an 06Z validity time that winds
# up in the um2netcdf output filename, whereas our system currently
# expects 00Z.  The 6 hour difference apparently doesn't matter to
# Globalwave so long is the filename is as expected, so we just need to
# rename the output file.  um2netcdf doesn't allow users to specify the
# full output filename (just pre- and post-fix strings that surround a
# cycle time extracted from the file) so I'll use a bizarre prefix
# to identify the initial output file.

# Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
SERVICE="globalnwp_conv_seaice"

PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d%T%Z`; $msgout Started"
echo "$MSG"

$NAGIOS $SERVICE OK $MSG

# Convert sea ice file
gunzip -c /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/output/*_${CYCLE_TIME}_ice.gz \
    > sls_${CYCLE_TIME}_seaice
/$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/um2netcdf -f -t -g /$SYSTEM/ecoconnect/wave_$SYSTEM/control/globalwave_120/attribute_sls_global.txt \
    -o sls_${CYCLE_TIME}_fake_ \
    sls_${CYCLE_TIME}_seaice
CC=$?
if ((CC!=0)); then
    MSG="$msgout um2netcdf of seaice failed"
    echo "`date -u +%Y%m%d%T%Z`; $MSG"
    $NAGIOS $SERVICE CRITICAL $MSG
    cylc task-message -p CRITICAL "$MSG"
    cylc task-failed
    exit 1
fi

rm sls_${CYCLE_TIME}_seaice  # remove the unpacked UM file
# rename the output netcdf file (and report it to stdout, because 
# um2netcdf reports creation of replace_me_*.nc)

REFDATE=${CYCLE_TIME:0:8}
REFHOUR=${CYCLE_TIME:8:2}

mv sls_${CYCLE_TIME}_fake_*.nc /$SYSTEM/ecoconnect/wave_${SYSTEM}/input/globalwave_120/sls_${CYCLE_TIME}_utc_global_seaice.nc

# copy for RiCOM
# TO DO: RICOM SHOULD COPY THIS FROM NWP OUTPUT DIR
#cp sls_${CYCLE_TIME}_utc_global_{seaice,sfcwind}.nc /$SYSTEM/ecoconnect/sea_level_$SYSTEM/input/ricom-nzl/
#cylc message "ricom global sea ice input file ready"
#cylc message "ricom global surface wind input file ready"

cylc task-message "SLS GLOBAL ICE for ${CYCLE_TIME} ready"

cylc task-finished
echo "`date -u +%Y%m%d%T%Z`; $msgout Finished"
exit 0
