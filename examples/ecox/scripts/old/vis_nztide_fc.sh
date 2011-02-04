#!/bin/bash

# Run the nztide-12 ivisualisation script.

# INTENDED USER:
# * sea_level_(dvel|test|oper)

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started 

#--------------------------------------
#  Set variables:
#
# Top directory (= /oper/sea_level_oper on pa)
TOPDIR="$HOME"
#
# Working directory
WORKDIR="$TOPDIR/running/nztide_12"

# create working directory if it doesn't exist
[[ ! -d $WORKDIR ]] && mkdir -p $WORKDIR

# Directory with NetCDF conversion utility executables:
NCDIR="$HOME/bin/netcdf"
#

# Visualisation script:
VISSCRIPT="$HOME/bin/scripts/vis_nztide_fc"

cd $WORKDIR

#   Get the new run start time from resulting log file
    read STIME1 < advtime.log

#
# Run visualisation:
if test -n "$VISSCRIPT"
   then
      if $VISSCRIPT $STIME1
         then
            echo "visualisation completed"
         else
            echo "visualisation failed"
            exit 1
      fi
fi

#
echo "$0 complete"
#

cylc message --finished
