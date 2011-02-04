#!/bin/bash
# Converts any UM file to netcdf
#
# This is a cycl wrapped script
#
# Author: Bernard Miville
# Date: 26 August 2010
#
# Environment variables:
# 1. FILEIN         - Input filename
# 2. FILEIN_LOC     - Input file location
# 3. FILEOUT        - Output file name
# 4. FILEOUT_LOC    - Output file location
# 5. FILEATT        - um2netcf file attribute
# 6. FILEATT_LOC    - file attribute location
# 7. MULTIFILE      - 0 Single file conversion (use FILEOUT)
#                     1 Multiple file conversion (do not use FILEOUT)
# 8. GUNZIP         - 0 Do not unzip the FILEIN (already unzipped)
#                     1 Unzip the FILEIN
# 9. UM2NC_O        - Name of output prefix (without .nc)
# 10. UM2NC_P       - Name of of output suffix (after timestamp)
# 11. UM2NC_CT      - Cycle time created by um2netcdf. Most of the time
#                   - it is equal to the CYCLE_TIME except for the global seaice file where
#                   - there is a 6 hour difference. 
# 12. FIELDS        - Fields to convert (enter space separated stash number or All for
#                     all fields)
# 13. OPTIONS       - List of options
# 14. SERVICE       - Name of NAGIOS service

# Trap errors so that we need not check the success of basic operations.
set -e

# Parameters
#### SYSTEM=${USER##*_}
#### . /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
NAGIOS=echo
#### PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"

# Print environment variables list
echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Arguments list:"
echo "   1-  FILEIN:         ${FILEIN}"
echo "   2-  FILEIN_LOC:     ${FILEIN_LOC}"
echo "   3-  FILEOUT:        ${FILEOUT}"
echo "   4-  FILEOUT_LOC:    ${FILEOUT_LOC}"
echo "   5-  FILEATT:        ${FILEATT}"
echo "   6-  FILEATT_LOC:    ${FILEATT_LOC}"
echo "   7-  MULTIFILE:      ${MULTIFILE}"
echo "   8-  GUNZIP:         ${GUNZIP}"
echo "   9-  UM2NC_O:        ${UM2NC_O}"
echo "  10-  UM2NC_P:        ${UM2NC_P}"
echo "  11-  UM2NC_CT:       ${UM2NC_CT}"
echo "  12-  OPTIONS:        ${OPTIONS}"
echo "  13-  FIELDS:	     ${FIELDS}"
echo "  14-  SERVICE:        ${SERVICE}"
echo "  15-  UM2NETCDF:      ${UM2NETCDF}"

if [ "${FIELDS}" = "All" ]; then
     FIELDS=" "
fi

# Check the environment variables
# Directories
cylcutil checkvars -d FILEIN_LOC \
                       FILEOUT_LOC \
                       FILEATT_LOC
                       
# Variables
cylcutil checkvars FILEIN \
                    FILEATT \
                    FILEOUT \
                    MULTIFILE \
                    GUNZIP \
                    UM2NC_O \
                    UM2NC_P \
                    UM2NC_CT \
                    OPTIONS \
                    FIELDS \
                    SERVICE \
                    UM2NETCDF

# Send NAGIOS OK message
$NAGIOS $SERVICE OK $msgout

# Loop for all files

cd ${FILEIN_LOC}

for UMFILE in ${FILEIN}; do
    # Unzip file if needed 
    if [ $GUNZIP -eq 1 ]; then
        gunzip -c ${UMFILE} > ${UMFILE}.unzip
    else
        mv ${UMFILE} ${UMFILE}.unzip
    fi

    # Convert UM file to NetCDF
####    if ! /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/um2netcdf $OPTIONS -g ${FILEATT_LOC}/${FILEATT} -o ${UM2NC_O} -p ${UM2NC_P} $FIELDS  ${UMFILE}.unzip; then
    if ! $UM2NETCDF $OPTIONS -g ${FILEATT_LOC}/${FILEATT} -o ${UM2NC_O} -p ${UM2NC_P} $FIELDS  ${UMFILE}.unzip; then
        MSG="$msgout um2netcdf of ${UMFILE} in ${FILEIN_LOC} failed"
        echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
        $NAGIOS $SERVICE CRITICAL $MSG
        cylc task-message -p CRITICAL "$MSG"
        exit 1
    fi
    
    if [ $GUNZIP -eq 1 ]; then
        rm ${UMFILE}.unzip
    else
        mv ${UMFILE}.unzip ${UMFILE}
    fi
    
    # UM2NETCDF_FILE is the file name given by um2netcdf program only
    # when the data time inside the UM file matches the CYCLE_TIME which is not always the
    # case (e.g. GLOBAL UM WIND file). If we want a different
    # final name and location and we are not converting multiple files, it
    # will then use the FILEOUT name instead.
    
    UM2NETCDF_FILE=${UM2NC_O}${UM2NC_CT}_utc${UM2NC_P}.nc 
    
    if [ $MULTIFILE -eq 1 ]; then
        FILEOUT=${UMFILE/.um/.nc}
    fi
    
    # Move NetCDF file(s) to final location
    if [ "${FILEIN_LOC}/${UM2NETCDF_FILE}" != "${FILEOUT_LOC}/${FILEOUT}" ]; then
        mv ${UM2NETCDF_FILE} ${FILEOUT_LOC}/${FILEOUT}
    fi
done

# Task finished
MSG="Finished"
echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
exit 0
