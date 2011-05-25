#!/bin/bash

# Hilary Oliver, NIWA, 2010

# Retrieve fieldsfiles from UM output directories (DATAM for sets of
# reinitialized PP files; DATAW for single PP files), and move them to
# final locations defined by cylc filename templates (see below):

# USAGE:
#  get-um-ouput.sh <UM RUNID> <PP STREAM LIST>
# For example:
#  get-um-output.sh xaald pp0 pp1 pc

# Corresponding filename templates must exist in the environment, e.g.:
#   OUT_pp0 = $DIR/tn_YYYYMMDDHH_utc_nzlam_12.um
#   OUT_pp1 = $DIR/sls_YYYYMMDDHH_utc_nzlam_12.um
#   OUT_pc  = $DIR/met_YYYYMMDDHH_utc_nzlam_12.um

# The HHH hour suffix on reinitialized files is transferred as follows:
# xaald_pc024 -> $DIR/met_YYYYMMDDHH_utc_nzlam_12_024.um

set -e

# get UM RUN ID:
RUNID=$1
shift

# find UM output directories
cylcutil checkvars -d DATAM_DIR DATAW_DIR
DATAM=$DATAM_DIR
DATAW=$DATAW_DIR

# loop through PP suffixes to process
for ITEM in $@; do
    if [[ $ITEM = pp* ]]; then
        # single PP files in DATAW

        export PPFILE=$DATAW/$RUNID.$ITEM 
        cylcutil checkvars -f PPFILE
 
        NAME=OUT_$ITEM
        # is ${OUT_$ITEM} defined?
        cylcutil checkvars $NAME

        export OUTFILE=$( eval "echo \$$NAME" )
        # ensure output file parent directory exists
        cylcutil checkvars -p OUTFILE

        echo "moving $PPFILE -> $OUTFILE"
        mv $PPFILE $OUTFILE
    else
        # multiple reinitialized PP files in DATAM

        NAME=OUT_$ITEM
        # is ${OUT_$ITEM} defined?
        cylcutil checkvars $NAME

        export OUTFILE_BASE=$( eval "echo \$$NAME" )

        PPFILES=$( ls $DATAM/${RUNID}a_${ITEM}??? )

        for PPFILE in $PPFILES; do
            SUFFIX=${PPFILE#*a_$ITEM}
            export OUTFILE=${OUTFILE_BASE%.um}_${SUFFIX}.um
            # ensure output file parent directory exists
            cylcutil checkvars -p OUTFILE
            echo "moving $PPFILE -> $OUTFILE"
            mv $PPFILE $OUTFILE
        done
    fi
done
