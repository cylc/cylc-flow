#!/bin/bash

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

# Purpose: Run the nztide-12 model. Can run anytime but it usually runds
# after the nzlam-12 is fisnihed at 6 and 18 UTC.

# Task-specific inputs: None

# INTENDED USER:
# * sea_level_(dvel|test|oper)

#--------------------------------------
#  Set variables:
#
# Time between runs: e.g. HH=+12 or +24
HH="+12"
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
# Directory with input (control) file:
CTLDIR="$HOME/control/nztide_12"
#
# Directory with input coefficient file:
INPDIR="$HOME/ancillary_data/nztide_12"
#
# Input coefficient file:
INPFILE="tide_coeffs_nz12.nc"
#
# Output directory:
OUTDIR="$TOPDIR/output/nztide_12"
#
# Prefix of output files, before timestamp:
OUTPRE="tide_"
#
# Suffix of output files, after timestamp:
OUTSUF="_utc_nztide_12.nc"
#
# File system "oper" or "test"
# Will work on sea_level_$FILESYS :
FILESYS=`echo $USER | cut -d_ -f3`
if test -z "$FILESYS"
# Will work on XXXX_$FILESYS :
  then
    FILESYS=`echo $USER | cut -d_ -f2`
fi
#
# Archive top directory:
ARCHDIR="/$FILESYS/archive"
#
# Visualisation script:
VISSCRIPT="$HOME/bin/scripts/vis_nztide_fc"
#
#--------------------------------------
# Display variables:
#
echo "-------------------------------"
echo "run_nztide_fc $1"
echo "-------------------------------"
echo "                  Time between runs: $HH"
echo "                        File system: $FILESYS"
echo "                      Top directory: $TOPDIR"
echo "                  Working directory: $WORKDIR"
echo "  Directory with NetCDF executables: $NCDIR"
echo "Directory with input (control) file: $CTLDIR"
echo "                    Input directory: $INPDIR"
echo "                   Output directory: $OUTDIR"
echo "             Prefix of output files: $OUTPRE"
echo "             Suffix of output files: $OUTSUF"
echo "              Archive top directory: $ARCHDIR"
echo "-------------------------------"

#
#--------------------------------------
#
# Process inputs
#
# Default argument for advtime:
ADVARG="$HH"
#
# Default run start time:
STIME=""
#
if test -n "$1"
  then
     STIME="$1"
     ADVARG="$STIME"
     echo "specified start time $STIME "
  else
# If no start time has been specified by user input, use fixed increment
     ADVARG=$HH
     echo "advancing start time by $HH "
fi
#--------------------------------------
#
cd $WORKDIR
#
# Get the input (control) file, if not already in the working directory:
if test -f tideforenc.inp
  then
     echo "  tideforenc.inp already in working directory"
  else
     cp $CTLDIR/tideforenc.inp .
     echo "  tideforenc.inp copied from $CTLDIR"
fi
#
# Get the input coefficients file, if not already in the working directory:
if test -f "./$INPFILE"
  then
     echo "  $INPFILE already in working directory"
  else
     cp $INPDIR/$INPFILE .
     echo "  $INPFILE copied from $INPDIR"
fi
#
# Advance times in input files, either by HH hours, or to match start time
if test -f tideforenc.inp
  then
    echo "calling advtimeT $ADVARG"
    $NCDIR/advtimeT $ADVARG
#
#   Get the new run start time from resulting log file
    read STIME1 < advtime.log
    echo "  tideforenc.inp rewritten with:"
    echo "  Start time: $STIME1"
#
  else
	cylc message -p CRITICAL "old tideforenc input file not found"
    cylc message --failed
    exit 1
fi
if test -f tideforenc.in2
  then
    mv -f tideforenc.inp tideforenc_old.inp
    mv -f tideforenc.in2 tideforenc.inp
  else
	cylc message -p CRITICAL "new tideforenc input file not found"
    cylc message --failed
	exit 1
fi
#
#-----------------------------------------
#
# Run Tide forecaster
$NCDIR/tideforenc
#
#-----------------------------------------
#
# Form YYYYMM string by removing last four characters from STIME1:
YYYYMM=${STIME1%????}
ARCHSUBDIR="$ARCHDIR/$YYYYMM"
#
echo "Archive subdirectory: $ARCHSUBDIR"
#
#   Make sure outputs are readable for others
chmod +r *.nc
#
OUTFILE="$OUTPRE$STIME1$OUTSUF"
if test -f $OUTFILE
  then
#   Copy outputs to local archive directory
     if test -d "$ARCHSUBDIR"
        then
           if test -f "$ARCHSUBDIR/$OUTFILE"
              then
                 echo " Output file $OUTFILE already exists in local archive directory $ARCHSUBDIR"
              else
                 if cp $OUTFILE $ARCHSUBDIR
                    then
                       echo " Output file $OUTFILE copied to local archive directory $ARCHSUBDIR"
                    else
                       echo " Unable to copy output file $OUTFILE to local archive directory $ARCHSUBDIR"
                 fi
           fi
        else
           echo " *** Output file $OUTFILE NOT copied to local archive directory $ARCHSUBDIR"
     fi
#   Move outputs to local output directory  
     mv -f ./$OUTFILE $OUTDIR/$OUTFILE
     echo " Output file $OUTFILE moved to $OUTDIR"
  else
	 cylc message -p CRITICAL "$OUTFILE not found"
     cylc message --failed
	 exit 1

fi
#
#

#
echo "$0 complete"

#
cylc message --succeeded
