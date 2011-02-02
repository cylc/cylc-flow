#!/bin/bash

ARCHIVE=$CYLC_DIR/dev/HousekeepingTest/ARC
rm -rf $ARCHIVE

TOPDIR=$CYLC_DIR/dev/HousekeepingTest/SRC
rm -r $TOPDIR
mkdir -p $TOPDIR

START=2010080806
END=2010081006
T=$START

while (( $T < $END )); do
    echo $T
    touch $TOPDIR/foo-${T}.nc
    touch $TOPDIR/bar-${T}.nc
    T=$( cylcutil cycletime -a 6 $T )
done
