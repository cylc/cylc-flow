#!/bin/bashXXX

set -e

# DO NOT RUN THIS COMMAND MANUALLY, IT IS A DARCS PREDIST SCRIPT.

trap "ABORTING PREDIST, DELETE THE NEW TARBALL IF DARCS CONTINUES!" ERR

echo "PRE MARCH 2009 (?) VERSIONS OF DARCS IGNORE NON-ZERO EXIT CODE IN"
echo "PREDIST SCRIPTS: WATCH FOR THIS AND DELETE THE RESULTING TARBALL!"

# a darcs predist script to:
#   - set executable permissions
#   - replace the cylc version tag in and main script and documentation 
#   - make documentation
#   - remove documentation source files

# TO CREATE A CLEAN CYLC DISTRIBUTION IN A NEW REPOSITORY:
# 1/ record any changes to this script
# 2/ darcs setpref predist 'sh bin/_cylc-predist.sh; rm bin/_cylc-predist.sh'
# 3/ final 'darcs tag'
# 4/ export CYLC_VERSION=[final version tag]
# 5/ darcs dist

if [[ -z $CYLC_VERSION ]]; then
    echo "\$CYLC_VERSION is not defined"
    echo "ABORTING PREDIST, DELETE THE NEW TARBALL IF DARCS CONTINUES!"
    exit 1
fi

echo "SETTING EXECUTABLE PERMISSIONS"

chmod +x bin/*

chmod +x doc/make-documentation.sh
chmod +x sys/examples/userguide/scripts/*
chmod +x sys/examples/nested/scripts/*
chmod +x sys/examples/distributed/scripts/*

echo "SETTING VERSION TAG IN MAIN COMMAND AND USERGUIDE"
perl -pi -e "s/-CYLC-VERSION-/$CYLC_VERSION/" bin/cylc
perl -pi -e "s/-CYLC-VERSION-/$CYLC_VERSION/" doc/userguide.tex

echo "MAKING DOCUMENTATION (USERGUIDE)"
# make sure documentation processing uses the release versions
# (which have the correct version tag inserted).
export PATH=bin:$PATH
export PYTHONPATH=src:$PYTHONPATH
doc/make-documentation.sh
echo "AGAIN, TO GET REFERENCES / TOC RIGHT(?)"
doc/make-documentation.sh

echo "DELETING DOCUMENTATION SOURCE"
cp doc/userguide.pdf .
rm -r doc
mkdir doc
mv userguide.pdf doc

echo "DELETING DEVELOPER DOCS"
rm README.todo

