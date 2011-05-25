#!/bin/bash
# Converts any UM file to netcdf
#
# Author: Bernard Miville
# Date: 6 August 2010
#
# Arguments:
# 1. FILEIN         - Input filename
# 2. FILEIN_LOC     - Input file location
# 3. FILEOUT        - Output file name
# 4. FILEOUT_LOC    - Output file location
# 5. FILEATT        - um2netcf file attribute
# 6. FILEATT_LOC    - file attribute location
# 7. GUNZIP         - 0 Do not unzip the FILEIN (already unzipped)
#                     1 Unzip the FILEIN
# 8. UM2NC_O        - Name of output prefix (without .nc)
# 9. UM2NC_P        - Name of of output suffix (after timestamp)
# 10. SERVICE       - Name of NAGIOS service
# 11. CYLC_MESSAGE  - Cylc message to send at successful completion
# 12. FILECOPY      - Copy filename (optional)
# 13. FILECOPY_LOC  - Copy filename location (optional)

# Trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR

# START MESSAGE
cylc task-started

# Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"

# Load arguments
FILEIN=$1
FILEIN_LOC=$2
FILEOUT=$3
FILEOUT_LOC=$4
FILEATT=$5
FILEATT_LOC=$6
GUNZIP=$7
UM2NC_O=$8
UM2NC_P=$9
SERVICE=${10}
CYLC_MESSAGE=${11}
FILECOPY=${12}
FILECOPY_LOC=${13}

# Print arguments list
echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Arguments list:"
echo "   1-  FILEIN:         ${FILEIN}"
echo "   2-  FILEIN_LOC:     ${FILEIN_LOC}"
echo "   3-  FILEOUT:        ${FILEOUT}"
echo "   4-  FILEOUT_LOC:    ${FILEOUT_LOC}"
echo "   5-  FILEATT:        ${FILEATT}"
echo "   6-  FILEATT_LOC:    ${FILEATT_LOC}"
echo "   7-  GUNZIP:         ${GUNZIP}"
echo "   8-  UM2NC_O:        ${UM2NC_O}"
echo "   9-  UM2NC_P:        ${UM2NC_P}"
echo "  10-  SERVICE:        ${SERVICE}"
echo "  11-  CYLC_MESSAGE:   ${CYLC_MESSAGE}"
echo "  12-  FILECOPY:       ${FILECOPY}"
echo "  13-  FILECOPY_LOC:   ${FILECOPY_LOC}"

# Check the number of required arguments
if [ "$#" -lt 11 ]; then
    # FATAL ERROR
    MSG="There needs to be 11 arguments present."
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    echo "`date -u +%Y%m%d" "%T" "%Z` $msgout $MSG"
    exit 1
fi

# Send NAGIOS OK message
$NAGIOS $SERVICE OK $msgout

# Unzip file is needed 
cd ${FILEIN_LOC}
if [ $GUNZIP -eq 1 ]; then
    gunzip -c ${FILEIN} > ${FILEIN}.unzip
else
    mv ${FILEIN} ${FILEIN}.unzip
fi

# Convert UM file to NetCDF
if ! /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/um2netcdf -f -t -i -g ${FILEATT_LOC}/${FILEATT} -o ${UM2NC_O} -p ${UM2NC_P} ${FILEIN}.unzip; then
    MSG="$msgout um2netcdf of $FILEIN in $FILELOC failed"
    echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
    $NAGIOS $SERVICE CRITICAL $MSG
    cylc task-message -p CRITICAL "$MSG"
    cylc task-failed
    exit 1
fi
    
if [ $GUNZIP -eq 1 ]; then
    rm ${FILEIN}.unzip
else
    mv ${FILEIN}.unzip ${FILEIN}
fi

# Copy file to another location if requested
if [ "$FILECOPY_LOC" -a "$FILECOPY" ]; then
    cp ${UM2NC_O}*${UM2NC_P}.nc ${FILECOPY_LOC}/${FILECOPY}
fi

# Move NetCDF file to final location
mv ${UM2NC_O}*${UM2NC_P}.nc ${FILEOUT_LOC}/${FILEOUT}

# Send message to cylc
cylc task-message ${CYLC_MESSAGE}

# Task finished
MSG="Finished"
echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
cylc task-finished
exit 0
