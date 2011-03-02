#!/bin/bash

# register example suites
# create central database
# export the example suites

# TO DO: use src/registrations to determine name of the central database
# in case it ever changes.

if [[ -z CYLC_DIR ]]; then
    echo "export \$CYLC_DIR and source \$CYLC_DIR/cylc-env.sh"
    echo "before running this script."
    exit 1
fi

echo
echo " + Registering examples suites"
cylc register cylc:userguide $CYLC_DIR/examples/userguide
cylc register cylc:simple $CYLC_DIR/examples/simple
cylc register dev:userguide $CYLC_DIR/dev/suites/userguide

echo
echo " + Exporting examples suites to the central database"
# Export the example suites to the central database.
# This will create the new database file.
cylc export -g cylc

echo
echo " + Setting central database permissions"
# The central database is currently hardwired to:
#   $CYLC_DIR/CentralDB/registrations.

# Make it writeable by all.
# (could be just g+w if all cylc users are in the same group).
chmod go+rx $CYLC_DIR/CentralDB
chmod go+rw $CYLC_DIR/CentralDB/registrations

echo "DONE"
