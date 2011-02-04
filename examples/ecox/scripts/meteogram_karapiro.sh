#!/bin/bash
#
# meteogram_karapiro
# 
# Trevor Carey-Smith - 2010-10-29
#
# Requires R, and R packages: RNetCDF,MOStools

set -e; trap 'cylc task-failed' ERR

SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh

# NAGIOS service
SERVICE=meteogram_karapiro

cylc task-started
MSG="$PROG_NAME starting for ${CYCLE_TIME}"
$NAGIOS $SERVICE OK $MSG

MODEL_NAME=nzlam
MODEL_GRID=12

RUNNINGPATH=$HOME/running/${MODEL_NAME}_${MODEL_GRID}/mos_karapiro

mkdir -p $RUNNINGPATH

cd $RUNNINGPATH
/oper/admin/mos_admin/bin/plotmeteogram_dvel -w 720 -s 'Karapiro Cws' -O -i wind,cloud,precip,temp -o Karapiro -p $RUNNINGPATH $CYCLE_TIME

ftp -u ftp://niwamedia:media55@ftp.niwa.co.nz/exclusive/ Karapiro.png
ftp -u ftp://anonymous:ecoconnect@ftp.niwa.co.nz/incoming/Karapiro/ Karapiro.png

cylc task-finished
MSG="$PROG_NAME finished for ${CYCLE_TIME}"
$NAGIOS $SERVICE OK $MSG

exit 0
