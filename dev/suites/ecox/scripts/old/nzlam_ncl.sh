#!/bin/bash

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

# Purpose: generate eps plots from the nzlam_12 met netcdf files 

# Task-specific input: None

SYS=${USER#*_}

NTHREADS=8
TMPDIR=/tmp_$SYS
CMD_FILE=$(mktemp -t $TASK_NAME.XXXXXXXXXX) || {
    cylc message -p CRITICAL "failed to make temp file"
    cylc message --failed
    exit 1 
}

NCL=/$SYS/ecoconnect/vis_$SYS/bin/ncl_scripts
OROG=/$SYS/ecoconnect/vis_$SYS/ancillary_data/nzlam-12-orography.nc

# model input (netcdf)
INDIR=/$SYS/ecoconnect/nwp_$SYS/output/nzlam_12

# CONSTRUCT AN NCL COMMAND FILE.
# use dummy arguments to make sure all lines have the same number of arguments 
# (this is required to use xargs for threading, below) 

# areal output dir
OUTA=/$SYS/ecoconnect/nwp_$SYS/running/nzlam_12/product/areal
[[ -d $OUTA ]] || mkdir -p $OUTA

# site-specific output dir
OUTS=/$SYS/ecoconnect/nwp_$SYS/running/nzlam_12/product/site_specific
[[ -d $OUTS ]] || mkdir -p $OUTS

# xml output dir
OUTX=$OUTS

# match input netcdf filenames
NCF="met_${CYCLE_TIME}_utc_nzlam_12_0??.nc"
   
# areal scripts with intervals
for INT in 6 12 24; do
	echo "'pin=\"$INDIR\"' 'f=\"$NCF\"' 'tref=\"UTC\"' 'interval=$INT' 'pout=\"$OUTA\"' 'foo=\"foo\"'    $NCL/atp_nzlam-12.ncl" >> $CMD_FILE
	echo "'pin=\"$INDIR\"' 'f=\"$NCF\"' 'tref=\"UTC\"' 'interval=$INT' 'pout=\"$OUTA\"' 'orog=\"$OROG\"' $NCL/ats_nzlam-12.ncl" >> $CMD_FILE
done

# other areal scripts
SCRIPTS="cldw10mmslp_nzlam-12.ncl \
hpaw10m_nzlam-12.ncl \
rh1p5m_nzlam-12.ncl \
t1p5m_nzlam-12.ncl \
w10mmslp_nzlam-12.ncl"

for SCRIPT in $SCRIPTS; do
	echo "'pin=\"$INDIR\"' 'f=\"$NCF\"' 'tref=\"UTC\"' 'foo=\"foo\"'   'pout=\"$OUTA\"' 'bar=\"bar\"'    $NCL/$SCRIPT" >> $CMD_FILE
done

# site specific script, no xml output (don't supply 'xout' argument)
echo "'pin=\"$INDIR\"' 'f=\"$NCF\"' 'tref=\"UTC\"' 'foo=\"foo\"'   'pout=\"$OUTS\"' $NCL/ssf_nzlam-12_mintaka.ncl" >> $CMD_FILE

# now run the ncl commands $NTHREADS at a time
cat $CMD_FILE | xargs --verbose --max-procs=$NTHREADS --max-args=7 ncl

cylc message --succeeded
