#!/bin/bash

ARCHIVE=$PWD/dev/HousekeepingTest/ARC
rm -rf $ARCHIVE

TOPDIR=$PWD/dev/HousekeepingTest/SRC
rm -rf $TOPDIR
mkdir -p $TOPDIR

START=2010080806
END=2010081006
T=$START

while (( $T < $END )); do
    echo $T
    touch $TOPDIR/foo-${T}.nc
    touch $TOPDIR/bar-${T}.nc
    T=$( cylc util cycletime -a 6 $T )
done
