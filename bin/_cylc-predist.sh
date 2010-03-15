#!/bin/bash

set -e

# a darcs predist script to:
#   - set executable permissions
#   - replace the cylc version tag in and main script and documentation 
#   - make documentation
#   - remove documentation source files

# you must export $CYLC_VERSION before running 'darcs dist' in the
# repository.

if [[ -z $CYLC_VERSION ]]; then
    echo "\$CYLC_VERSION is not defined"
    exit 1
fi

chmod +x bin/*

chmod +x sys/examples/userguide/scripts/*
chmod +x sys/examples/nested/scripts/*
chmod +x sys/examples/distributed/scripts/*

perl -pi -e "s/-CYLC-VERSION-/$CYCL_VERSION/" bin/cylc
perl -pi -e "s/-CYLC-VERSION-/$CYCL_VERSION/" doc/userguide.tex

doc/make-documentation.sh

cp doc/userguide.pdf .
rm -r doc
mkdir doc
mv userguide.pdf doc
