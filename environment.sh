#!/bin/bashX # <-- prevent accidental non-dot-run!

# Source (dot-run) this script to configure your shell for THIS cylc.

# You must move to the top level of your cylc installation before
# sourcing this script OR first set $CYLC_DIR to that directory.

# Note that any reference to an environment variable which could
# potentially be undefined is wrapped in ${VAR:-} for compatibility
# with 'set -u' (thanks to Dave Matthews, Met Office).

if [[ -f bin/cylc ]]; then
    # we're in the top level of a cylc installation
    CYLC_DIR=$PWD

elif [[ -n ${CYLC_DIR:-} ]]; then
    if [[ ! -f $CYLC_DIR/bin/cylc ]]; then
        echo "ERROR: $CYLC_DIR is not a cylc installation"
        return 1
    elif [[ ! -x $CYLC_DIR/bin/cylc ]]; then
        echo "ERROR: $CYLC_DIR/bin is not executable"
        return 1
    fi
else
    echo "ERROR: you must export \$CYLC_DIR before sourcing me,"
    echo "  OR otherwise move to \$CYLC_DIR before sourcing me."
    return 1
fi

# If we reach this line $CYLC_DIR is defined and valid.

if [[ ! -x $CYLC_DIR/bin/cylc ]]; then
    echo "ERROR: $CYLC_DIR/bin/cylc is not executable"
    return 1
fi

echo "CONFIGURING THIS SHELL FOR $CYLC_DIR/bin/cylc"
export CYLC_DIR

# remove any previous cylc path settings 
PATH=$($CYLC_DIR/bin/_clean-path ${PATH:-})
PYTHONPATH=$($CYLC_DIR/bin/_clean-path ${PYTHONPATH:-})

# export PATH to cylc bin
PATH=$CYLC_DIR/bin:$CYLC_DIR/util:$PATH

# export PYTHONPATH to cylc core source modules
PYTHONPATH=$CYLC_DIR/src:$CYLC_DIR/src/job-submission:$CYLC_DIR/src/task-types:$CYLC_DIR/src/locking:$CYLC_DIR/src/gui:$CYLC_DIR/src/external:$CYLC_DIR/src/prerequisites/$PYTHONPATH
PYTHONPATH=$CYLC_DIR/conf:$PYTHONPATH

# FOR LOCAL INSTALLATION OF PYRO, GRAPHVIZ, AND PYGRAPHVIZ
# Uncoment below and adjust paths appropriately for your system.
# See the Cylc User Guide "Installation" Section for detailed instructions. 
# PYTHONPATH=$CYLC_DIR/external/installed/lib64/python2.6/site-packages:$PYTHONPATH
# PATH=$CYLC_DIR/external/installed/bin:$PATH

if [[ -n ${CYLC_SUITE_DIR:-} ]]; then
    # caller must be a cylc job script; add suite-specific paths as well
    PATH=$CYLC_SUITE_DIR/bin:$PATH
fi

export PATH
export PYTHONPATH

# Python stdout buffering delays appearance of output when not directed
# to a terminal (e.g. when running a suite via the poxix nohup command).
export PYTHONUNBUFFERED=true

VERSION=$( cylc -v )
# ('cylc -v' fails if Pyro is not installed)
if [[ $? == 0 ]]; then
    echo "Cylc release version: $VERSION"
fi

# Export $HOSTNAME for use in default lockserver config (see
# $CYLC_DIR/conf/lockserver.conf). HOSTNAME is a bash variable (see man
# bash) that is defined but not exported; in other shells it may not
# even be defined.
export HOSTNAME=$(hostname)
