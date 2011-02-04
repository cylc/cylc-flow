#!/bin/bash

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

# Purpose: run the globalwave model

# task-specific inputs: None

SYSTEM=${USER##*_}
SUPERCOMPUTER=kupe

cd $HOME/input/globalwave_120

# copy files to kupe:/oper/wave_oper/input/globalwave_120
# TO DO: SHOULD GLOBAL NWP TASKS COPY THE FILES TO MY INPUT DIR, OR SHOULD I GET THEM FROM NWP OUTPUT DIR? (CONSIDER WHO IS TO ARCHIVE?)
for file in $HOME/input/globalwave_120/sls_${CYCLE_TIME}_utc_global_{seaice,sfcwind}.nc
do
    remote=`basename $file`
    curl --netrc --silent --upload-file $file \
            ftp://$SUPERCOMPUTER/input/globalwave_120/$remote
    if (( $? )) ; then 
	# the upload  didn't work
	MSG="transfer to $SUPERCOMPUTER failed for $remote, curl error $?"
    cylc message -p CRITICAL "$MSG"
    cylc message --failed
	exit 1
    fi
done

# qsub job on kupe
if [ $COLD ]; then 
    ssh $SUPERCOMPUTER ". /opt/modules/modules/init/ksh ; module load nqe mpt; bin/scripts/init_global_fc $CYCLE_TIME"
    if (( $? )) ; then 
	# the init didn't work
	MSG="$PROG_NAME couldn't initialise global wave forecast on  $SUPERCOMPUTER"
    cylc message -p CRITICAL "$MSG"
    cylc message --failed
	exit 1
    fi
fi

MAX_REQ_TIME=3600 # seconds = 60 minutes. Per request max CPU time

ssh $SUPERCOMPUTER "cd running; . /opt/modules/modules/init/ksh ; module load nqe ; CYCLE_TIME=$CYCLE_TIME qsub -x -q ecoconnect_$SYSTEM -l mpp_p=216 -l mpp_t=$MAX_REQ_TIME ../bin/scripts/run_global_fc"
if (( $? )) ; then 
    # the qsub didn't work
    MSG="$PROG_NAME couldn't qsub global wave forecast on $SUPERCOMPUTER"
    cylc message -p CRITICAL "$MSG"
    cylc message --failed
    exit 1
fi
cylc message "$PROG_NAME submitted for $CYCLE_TIME"

# archive input files 
nice bzip2 --best sls_${CYCLE_TIME}_utc_global_{seaice,sfcwind}.nc
mv sls_${CYCLE_TIME}_utc_global_{seaice,sfcwind}.nc.bz2 $ARCHIVE_DIR/
if (( $? )) ; then
    # the archiving failed didn't work
    MSG="$PROG_NAME archiving of wind and ice files failed"
    cylc message -p CRITICAL "$MSG"
    cylc message --failed
    exit 1
fi
