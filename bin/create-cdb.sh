#!/bin/bash

set -e

# This script creates the central suite database and registers the
# cylc example suites in it. Rerunning it will cause no ill effects.

# Steps:
# 1/ register the example suites in the cylc owner's local db
# 2/ export the example suites to the central database
# 3/ set central db file permissions appropriately

if [[ -z CYLC_DIR ]]; then
    echo "export \$CYLC_DIR and source \$CYLC_DIR/environment.sh"
    echo "before running this script."
    exit 1
fi

echo
echo " + Registering examples suites"
cylc register examples:userguide $CYLC_DIR/examples/userguide
cylc register examples:simple $CYLC_DIR/examples/simple
#cylc register dev:userguide $CYLC_DIR/dev/suites/userguide

echo
echo " + Exporting examples suites to the central database"
# Export the example suites to the central database.
# This will create the new database file.
cylc export examples:

# determine CDB directory location
CDB=$(python -c 'from CylcGlobals import central_regdb_dir; print central_regdb_dir')

echo
echo " + Setting central database permissions"

# Make the central db writeable by all.
# (could be just g+w if all cylc users are in the same group).
chmod go+rwx $CDB
chmod go+rw $CDB/db

echo "DONE"
