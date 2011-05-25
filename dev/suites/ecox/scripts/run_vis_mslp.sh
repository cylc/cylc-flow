#!/bin/bash
#
# Visualisation of 5 day Mean Sea Level Pressure
#
# This is a cylc wrapped script
#
# Syntax: vis_mslp [yyyymmddhh]
#     Use time stamp yyyymmddhh to specify the run start time.
#     Otherwise env. variable CYCLE_TIME is used 
#
# Trap errors so that we need not check the success of basic operations.
set -e

#
# to differentiate between oper and test systems
SYSTEM=${USER##*_}

SERVICE="globalnwp_ncl"

. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh

PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d%T%Z`; $msgout Started"
echo "$MSG"
$NAGIOS $SERVICE OK $MSG

TOPDIR="$HOME"

# Eps output directory:
OUTDIR="$TOPDIR/running/global/product"
#
# Directory with ncl scripts:
NCLDIR="/$SYSTEM/ecoconnect/vis_$SYSTEM/bin/ncl_scripts"
#
# UM model output directory:
INDIR=${SRCE_DIR}
NCFILE=${SRCE_FILENAME}

if [ -z $CYCLE_TIME ]; then
	 CYCLE_TIME=$1 
fi

ncl 'pin="'$INDIR'"' 'f="'$NCFILE'"' 'tref="UTC"' 'pout="'$OUTDIR/areal'"' \
  $NCLDIR/w10mmslp_global.ncl &

ncl 'pin="'$INDIR'"' 'f="'$NCFILE'"' 'tref="UTC"' 'pout="'$OUTDIR/areal'"' \
  'interval=12' $NCLDIR/atp_n320l50.ncl &

ncl 'pin="'$INDIR'"' 'f="'$NCFILE'"' 'tref="UTC"' 'pout="'$OUTDIR/areal'"' \
  'interval=24' $NCLDIR/atp_n320l50.ncl &

ncl 'pin="'$INDIR'"' 'f="'$NCFILE'"' 'tref="UTC"' 'pout="'$OUTDIR/areal'"' \
  $NCLDIR/paw10m_n512l70.ncl &

ncl 'pin="'$INDIR'"' 'f="'$NCFILE'"' 'tref="UTC"' 'pout="'$OUTDIR/areal'"' \
  $NCLDIR/t1p5m_n320l50.ncl &

ncl 'pin="'$INDIR'"' 'f="'$NCFILE'"' 'xout="'$OUTDIR/site_specific'"' \
  $NCLDIR/ssf_n320l50_mintaka.ncl &

wait


# TO DO: check when to remove this, now that nwp_$SYS does global vis
# clean up input file (already archived by run_globalwave_120)
#rm $INDIR/sls_${CYCLE_TIME}_utc_global_sfcwind.nc

# Signal to the controller script that the run is finished
case $? in
    0)
        # All is good
        # SUCCESS MESSAGE
        MSG="`date -u +%Y%m%d%T%Z`; $msgout Finished"
        echo $MSG
        $NAGIOS $SERVICE OK $MSG
        ;;
    *)
        # There was a problem
        MSG="vis_mslp failed for $CYCLE_TIME"
        echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
        cylc task-message -p CRITICAL $MSG
        $NAGIOS $SERVICE CRITICAL $MSG
	    exit 1
        ;;
esac
