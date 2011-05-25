#!/bin/bash
# Clean NetCDF file
#
# This is a cylc wrapped task
#
# Author: Bernard Miville
# Date: 26 August 2010
#
# Environment variables:
# 1. FILEIN         - Input filename
# 2. FILEIN_LOC     - Input file location
# 3. FILEOUT        - Output file name
# 4. FILEOUT_LOC    - Output file location
# 5. SERVICE        - Name of NAGIOS service

# Trap errors so that we need not check the success of basic operations.
set -e

# Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"
LLCLEAN=/$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/llclean

# Print environment variables list
echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Arguments list:"
echo "   1-  FILEIN:         ${FILEIN}"
echo "   2-  FILEIN_LOC:     ${FILEIN_LOC}"
echo "   3-  FILEOUT:        ${FILEOUT}"
echo "   4-  FILEOUT_LOC:    ${FILEOUT_LOC}"
echo "   5-  SERVICE:        ${SERVICE}"

# Check the environment variables
# Directories
cylcutil check-vars -d FILEIN_LOC \
                       FILEOUT_LOC
# Variables
cylcutil check-vars FILEIN \
                    FILEOUT \
                    SERVICE

# Send NAGIOS OK message
$NAGIOS $SERVICE OK $msgout

cd ${FILEIN_LOC}

# Clean NetCDF file
if $LLCLEAN -o temp_${FILEIN} ${FILEIN}; then
	# Move file to final location
	mv temp_${FILEIN}.nc ${FILEOUT_LOC}/${FILEOUT}
    else
	MSG="Failed to llclean the file ${FILEIN}"
	echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
	$NAGIOS $SERVICE CRITICAL $MSG
	cylc task-message -p CRITICAL "$MSG"
	exit 1
fi

# Task finished
MSG="Finished"
echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
exit 0
