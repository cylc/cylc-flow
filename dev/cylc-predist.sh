#!/bin/bashXXX

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


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
chmod +x scripts/*
chmod +x doc/process
chmod +x systems/trivial/scripts/*
chmod +x systems/userguide/scripts/*
chmod +x systems/nested/scripts/*
chmod +x systems/distributed/scripts/*
chmod +x systems/scs-demo/scripts/*

echo "SETTING VERSION TAG IN MAIN COMMAND AND USERGUIDE"
perl -pi -e "s/THIS IS NOT A VERSIONED RELEASE/$CYLC_VERSION/" src/gtk/gtkmonitor.py
perl -pi -e "s/THIS IS NOT A VERSIONED RELEASE/$CYLC_VERSION/" bin/cylc
perl -pi -e "s/THIS IS NOT A VERSIONED RELEASE/$CYLC_VERSION/" doc/userguide.tex

echo "MAKING DOCUMENTATION (USERGUIDE)"
# make sure documentation processing uses the release versions
# (which have the correct version tag inserted).
export PATH=bin:$PATH
export PYTHONPATH=src:$PYTHONPATH
echo
echo "LATEX PROCESSING 1/3"
echo
doc/process
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
cp doc/userguide.pdf .
rm -r doc
mkdir doc
mv userguide.pdf doc

echo "DELETING UNUSED IMAGE FILES"
rm -r images/not-active

echo "DELETING DEV STUFF"
rm -r dev

echo "DELETING EXPERIMENTAL SYSTEMS"
rm -rf systems/experimental

echo "REMOVING ANY PYC FILES"
find . -name '*.pyc' | xargs rm
