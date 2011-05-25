#!/bin/bash

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

# Purpose: run the nzwave model
# Task-specific inputs: None

SYSTEM=${USER##*_}
SUPERCOMPUTER=kupe  # TO DO: put in general env?

NPROC_INIT=8
NPROC_RUN=216

MODEL=nzwave_12

# copy input from nzlam_12 output dir
if ssh $SUPERCOMPUTER "[[ -f input/$MODEL/sls_${CYCLE_TIME}_utc_nzlam_12.nc ]]"; then
   # for re-runs, nzlam file may already be in wave input dir
   echo "nzlam sls file already in place: input/$MODEL/sls_${CYCLE_TIME}_utc_nzlam_12.nc"
else 
   # copy it from nzlam output dir
   echo "copying nzlam sls file to: input/$MODEL/sls_${CYCLE_TIME}_utc_nzlam_12.nc"
   ssh $SUPERCOMPUTER "cd input/$MODEL; cp /$SYSTEM/nwp_$SYSTEM/output/nzlam_12/sls_${CYCLE_TIME}_utc_nzlam_12.nc ." || { 
	# can't copy input file
	MSG="couldn't copy sls_${CYCLE_TIME}_utc_nzlam_12.nc from nzlam_12 output on $SUPERCOMPUTER"
    cylc message -p CRITICAL "$MSG"
    cylc message --failed
	exit 1
   }
fi

# qsub job on kupe

case ${CYCLE_TIME:8:10} in
    00|12)
	PROG="an" # analysis
	;;

    06|18)
	PROG="fc" # forecast
	;;
esac

if [ $COLD ]; then 
	ssh $SUPERCOMPUTER "cd running; . /opt/modules/modules/init/ksh ; module load nqe ; CYCLE_TIME=$CYCLE_TIME qsub -x -q ecoconnect_$SYSTEM -l mpp_p=$NPROC_INIT ../bin/scripts/init_nzwave_$PROG"
    	if (( $? )) ; then 
		# the init didn't work
		MSG="couldn't initialise nzwave forecast on  $SUPERCOMPUTER"
        cylc message -p CRITICAL "$MSG"
        cylc message --failed
		exit 1
    	fi
fi

MAX_REQ_TIME=10800 # seconds = 180 minutes. Per request max CPU time

ssh $SUPERCOMPUTER "cd running; . /opt/modules/modules/init/ksh ; module load nqe ; CYCLE_TIME=$CYCLE_TIME qsub -x -q ecoconnect_$SYSTEM -l mpp_p=$NPROC_RUN -l mpp_t=$MAX_REQ_TIME ../bin/scripts/run_nzwave_$PROG"
if (( $? )) ; then 
    # the qsub didn't work
    MSG="couldn't qsub nzwave forecast on $SUPERCOMPUTER"
    cylc message -p CRITICAL "$MSG"
    cylc message --failed
    exit 1
fi

cylc message --succeeded
