#!/bin/bashXXX
# THIS IS A DARCS PREDIST SCRIPT.

set -e
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
# 2/ darcs setpref predist 'sh dev/cylc-predist.sh'
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
chmod +x util/*
chmod +x test/*
chmod +x doc/process
chmod +x examples/simple/bin/*
chmod +x examples/userguide/bin/*

echo "SETTING VERSION TAG IN MAIN COMMAND AND USERGUIDE"
perl -pi -e "s/THIS IS NOT A VERSIONED RELEASE/$CYLC_VERSION/" src/gui/gcylc.py
perl -pi -e "s/THIS IS NOT A VERSIONED RELEASE/$CYLC_VERSION/" src/gui/SuiteControl.py
perl -pi -e "s/THIS IS NOT A VERSIONED RELEASE/$CYLC_VERSION/" bin/cylc
perl -pi -e "s/THIS IS NOT A VERSIONED RELEASE/$CYLC_VERSION/" doc/userguide.tex
perl -pi -e "s/THIS IS NOT A VERSIONED RELEASE/$CYLC_VERSION/" README

echo "MAKING DOCUMENTATION (USERGUIDE)"
# make sure documentation processing uses the release versions
# (which have the correct version tag inserted).
export PATH=bin:$PATH
export PYTHONPATH=src:$PYTHONPATH
echo
echo "LATEX PROCESSING 1/3"
echo
doc/process -c -f
echo
echo "LATEX PROCESSING 2/3"
echo
doc/process
# Third time required to get Table of Contents page number right?!
echo
echo "LATEX PROCESSING 3/3"
echo
doc/process

echo "DELETING DOCUMENTATION SOURCE"
# copy and restore from doc/:
#  1/ the PDF userguide
#  2/ SuiteDesign.txt
#  3/ suite.rc.README
# (2 and 3 are required by 'cylc configure', which copies them into
# suite defintion directores for the endless edification of users).
cp doc/userguide.pdf .
cp doc/SuiteDesign.txt .
rm -r doc
mkdir doc
mv userguide.pdf doc
mv SuiteDesign.txt doc

echo "DELETING DEV DIRECTORY"
rm -r dev

echo "REMOVING .pyc FILES"
find . -name '*.pyc' | xargs rm
