s#!/bin/bash

# Hilary Oliver 

# What this script does, in order:

# 1/ (all cycles)
#    retrieve the sls UM file from kupe
#      convert it to netcdf
#        copy the netcdf file back to kupe, for nzwave

# 2/ (06 and 18Z only)
#    retrieve the tn UM file from kupe
#      convert it to netcdf

# 3/ (06 and 18Z only)
#    retrieve the met UM files from kupe
#      convert them to netcdf
#        qsub nzlam_12_generate_eps

# Transferring the UM files from kupe is by far the most time consuming
# part of this script, so we check to see if the UM files have already
# been transferred in a previous run before doing the ftp copy (manual
# reruns of process_nzlam_output have sometimes been required in the
# operation).

# Some of this could be done in parallel, but that isn't going to help
# transfer time to and from kupe, which is currently the bottleneck.
# Also, we could do the met files first instead of last, to get the
# nzlam products out a few minutes faster, but that would hold back
# nzwave, ricom, and topnet somewhat.

function log
{
    MSG=$@
    echo $MSG
    $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG
    $NAGIOS $SERVICE OK $MSG
}

function warn
{
    MSG=$@
    echo "WARNING: $MSG"
    $LOGGER -i -p $FACILITY.warning -t $PROG_NAME $MSG
    $NAGIOS $SERVICE WARNING $MSG
}

function error
{
    MSG=$@
    echo "ERROR: $MSG"
    $LOGGER -i -p $FACILITY.crit -t $PROG_NAME $MSG
    $NAGIOS $SERVICE CRITICAL $MSG
}

function retrieve_um_files
{
    # retrieve_um_files <filename prefix (e.g. "met")> 
    # get specified UM files for the current $REFERENCE_TIME

    PREFIX=$1

    log "retrieving $PREFIX UM file(s) for $REFERENCE_TIME"

    ftp -i ${SUPERCOMPUTER}<<eof
bin
cd $REMOTE_STAGING_DIR
mget ${PREFIX}*_${REFERENCE_TIME}_*.um
bye
eof
}

function convert_um_to_nc
{
    # convert_um_to_nc <UM file prefix> <netcdf global attr file> <field list>

    PREFIX=$1; ATTR=$2
    shift 2
    FIELDS=$@

    __fail=false
    for UMFILE in ${PREFIX}*_${REFERENCE_TIME}_*.um; do

        log "converting $UMFILE to netcdf"

        if $UM2NETCDF -f -t -i -c -g $ATTR -o temp $FIELDS $UMFILE; then
            # rename the new netcdf file 
            mv temp${REFERENCE_TIME}_utc.nc ${UMFILE%.um}.nc

        else
            error "failed to convert $UMFILE to netcdf"
            __fail=true

            log "moving $UMFILE to conv-failures directory"
            [[ ! -d conv-failures ]] && mkdir conv-failures
            mv $UMFILE conv-failures
            rm -f temp${REFERENCE_TIME}_utc.nc
        fi
    done

    $__fail && return 1
    return 0
}

# Trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR

SYS=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh

SERVICE=process_nzlam_output

if [[ $# == 1 ]]; then
    CYCLE_TIME=$1
fi

if [[ -z $CYCLE_TIME ]]; then
    error "\$CYCLE_TIME not defined"
    exit 1
fi

log "starting for $REFERENCE_TIME"

SUPERCOMPUTER=fitzroy
UM2NETCDF=/$SYS/ecoconnect/ecoconnect_$SYS/bin/um2netcdf
LLCLEAN=/$SYS/ecoconnect/ecoconnect_$SYS/bin/llclean

REMOTE_STAGING_DIR=output/nzlam_12/netcdf_staging

OUTPUT_DIR=$HOME/output/nzlam_12
[[ ! -d $OUTPUT_DIR ]] && mkdir -p $OUTPUT_DIR

# netcdf global attributes and list of fields to convert
#   topnet
TN_ATTR=$HOME/control/nzlam_12/netcdf-attr/attribute_tn_nzlam-12.txt
TN_FIELDS="33 409 1235 2207 3236 3209 3210 3245 5226"
#   sls
SLS_ATTR=$HOME/control/nzlam_12/netcdf-attr/attribute_sls_nzlam-12.txt
SLS_FIELDS=""
#   met
MET_ATTR=$HOME/control/nzlam_12/netcdf-attr/attribute_met_nzlam-12.txt
MET_FIELDS="23 24 33 409 3209 3210 3236 3245 3248 3281 3282 3283 4201 4203 5201 5205 5215 5216 5226 6203 8223 9203 9204 9205 9216 15229 15242 15243 15244 16202 16203 16222 16256"
#   escape
ESC_ATTR=$HOME/control/nzlam_12/netcdf-attr/attribute_escape_nzlam-12.txt
ESC_FIELDS=""

# go to output directory
cd $HOME/output/nzlam_12

HOUR=${CYCLE_TIME#????????}
echo "HOUR is $HOUR"

# SLS FILE (copying not needed anymore, thanks to GPFS)
#if ls sls*_${CYCLE_TIME}_*.um > /dev/null 2>&1; then
#    warn "sls UM file already exists for $CYCLE_TIME; not recopying"
#    # delete the local file to force recopying!
#else
#    retrieve_um_files "sls"
#fi

if convert_um_to_nc "sls" $SLS_ATTR $SLS_FIELDS; then
    # sls netcdf file needed by nzwave
#    log "copying sls netcdf file to $SUPERCOMPUTER for $REFERENCE_TIME"
#    ftp -i ${SUPERCOMPUTER}<<eof
#bin
#cd output/nzlam_12
#mput sls_*${REFERENCE_TIME}*.nc
#bye
#eof
else
	echo "failed"
fi

if [[ $HOUR == 06 || $HOUR == 18 ]]; then

    # TN FILE
    if ls tn*_${REFERENCE_TIME}_*.um  > /dev/null 2>&1; then
        warn "tn UM file already exists for $REFERENCE_TIME; not recopying"
    else
        retrieve_um_files "tn"
    fi

    if convert_um_to_nc "tn" $TN_ATTR $TN_FIELDS; then

        log "llcleaning the tn netcdf file for $REFERENCE_TIME"
        # REQUIRED UNTIL WE CHANGE THE UM STASH GRID CUTOUT DEFINITION
        NCFILE=tn*_${REFERENCE_TIME}_*.nc
        if $LLCLEAN -o temp $NCFILE; then
            mv temp.nc $NCFILE
        else
            error "failed to llclean the tn netcdf file for $REFERENCE_TIME"
        fi
    fi

    # MET FILES
    N_MET_FILES=4
    if (( $( ls met*_${REFERENCE_TIME}_*.um | wc -l ) == $N_MET_FILES )); then
        warn "$N_MET_FILES met UM files already exist for $REFERENCE_TIME"
        # delete the local files to force recopying!
    else
        retrieve_um_files "met"
    fi

    convert_um_to_nc "met" $MET_ATTR $MET_FIELDS

    # ESCAPE FILES
    N_ESC_FILES=4
    if (( $( ls escape*_${REFERENCE_TIME}_*.um | wc -l ) == $N_ESC_FILES )); then
        warn "$N_ESC_FILES esc UM files already exist for $REFERENCE_TIME"
        # delete the local files to force recopying!
    else
        retrieve_um_files "escape"
    fi

    # TEMPORARILY DISABLED convert_um_to_nc "escape" $ESC_ATTR $ESC_FIELDS

    log "qsubbing nzlam_12_generate_eps for $REFERENCE_TIME"
    qsub -q $SYS -v REFERENCE_TIME -k oe /$SYS/nwp_$SYS/bin/nzlam_12_generate_eps
fi

log "finished for $REFERENCE_TIME"
