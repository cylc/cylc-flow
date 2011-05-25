#!/bin/bash

# Hilary Oliver, NIWA, 2010

# Retrieve fieldsfiles from UM output directories (DATAM for sets of
# reinitialized PP files; DATAW for single PP files), and move them to
# the suite output directory, renamed according to appropriate cycle
# time dependent filename templates.  The UM output dirs must be defined
# by cylc filename templates: TEMPLATE_DATAM_DIR and TEMPLATE_DATAW_DIR

# USAGE:
#  get-um-ouput.sh <UM RUNID> <PP STREAM LIST>
# 
# For example:
#  get-um-output.sh xaala pp0 pp1 pc

# Corresponding filename templates must exist in the environment, e.g.:
#  TEMPLATE_pp0 = $__NZLAM12_OUTPUT_DIR/tn_YYYYMMDDHH_utc_nzlam_12.um
#  TEMPLATE_pp1 = $__NZLAM12_OUTPUT_DIR/sls_YYYYMMDDHH_utc_nzlam_12.um
#  TEMPLATE_pc  = $__NZLAM12_OUTPUT_DIR/met_YYYYMMDDHH_utc_nzlam_12.um

# The HHH hour suffix on reinitialized files is transferred as follows:
# xaala_pc024 -> $__NZLAM12_OUTPUT_DIR/met_YYYYMMDDHH_utc_nzlam_12_024.um

set -e

# get UM RUN ID:
RUNID=$1
shift

# find UM output directories
cylcutil check-vars TEMPLATE_DATAM_DIR TEMPLATE_DATAW_DIR
DATAM=$( cylcutil template TEMPLATE_DATAM_DIR )
DATAW=$( cylcutil template TEMPLATE_DATAW_DIR )

# loop through PP suffixes to process
for ITEM in $@; do
    if [[ $ITEM = pp* ]]; then
        # single PP files in DATAW

        export PPFILE=$DATAW/$RUNID.$ITEM 
        cylcutil check-vars -f PPFILE
 
        TEMPLATE_NAME=TEMPLATE_$ITEM
        cylcutil check-vars $TEMPLATE_NAME

        export OUTFILE=$( cylcutil template $TEMPLATE_NAME )
        # ensure output file parent directory exists
        cylcutil check-vars -p OUTFILE

        echo "moving $PPFILE -> $OUTFILE"
        mv $PPFILE $OUTFILE
    else
        # multiple reinitialized PP files in DATAM

        TEMPLATE_NAME=TEMPLATE_$ITEM
        cylcutil check-vars $TEMPLATE_NAME

        PPFILES=$( ls $DATAM/${RUNID}a_${ITEM}??? )
        OUTFILE_BASE=$( cylcutil template $TEMPLATE_NAME )

        for PPFILE in $PPFILES; do
            SUFFIX=${PPFILE#*a_$ITEM}
            export OUTFILE=${OUTFILE_BASE%.um}_${SUFFIX}.um
            # ensure output file parent directory exists
            cylcutil check-vars -p OUTFILE
            echo "moving $PPFILE -> $OUTFILE"
            mv $PPFILE $OUTFILE
        done
    fi
done
