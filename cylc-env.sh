#!/bin/bashX # <-- prevent accidental non-dot-run!

# Source (dot-run) this script to configure your shell for THIS cylc.

# You must move to the top level of your cylc installation before
# sourcing this script OR first set $CYLC_DIR to that directory.

# THE FOLLOWING IS A PROBLEM IF WE NEED TO CONFIGURE CYLC ENV INSIDE A
# SHELL FUNCTION (SHELL FUNCTIONS CAN'T BE NESTED) - e.g. OPS and VAR
# WRAPPERS, AS CURRENTLY IMPLEMENTED.
#function cycl {
#    echo "TYPO ALERT: it's 'cylc' NOT 'cycl'!"
#    cylc $@
#    return 0
#}

if [[ -f bin/cylc ]]; then
    # we're in the top level of a cylc installation
    CYLC_DIR=$PWD

elif [[ ! -z $CYLC_DIR ]]; then
    if [[ ! -f $CYLC_DIR/bin/cylc ]]; then
        echo "ERROR: $CYLC_DIR is not a cylc installation"
        return 1
    elif [[ ! -x $CYLC_DIR/bin/cylc ]]; then
        echo "ERROR: $CYLC_DIR/bin is not executable"
        return 1
    fi
else
    echo "ERROR: source from top level cylc, or set CYLC_DIR"
    return 1
fi

if [[ ! -x $CYLC_DIR/bin/cylc ]]; then
    echo "ERROR: the cylc program here is not set executable:"
    echo " > $CYLC_DIR/bin/cylc"
    echo
    echo "If this is a cylc darcs repository, rather than an"
    echo "installed cylc release, you may need to do this:"
    echo " % cd $CYLC_DIR"
    echo " % chmod +x bin/* scripts/* systems/*/scripts/*"
    return 1
fi

echo "CONFIGURING THIS SHELL FOR $CYLC_DIR/bin/cylc"
export CYLC_DIR  # in case not exported already

# remove any previous cylc path settings 
PATH=$($CYLC_DIR/bin/_cylc-clean-path $PATH)
PYTHONPATH=$($CYLC_DIR/bin/_cylc-clean-path $PYTHONPATH)

# export PATH to cylc bin
PATH=$CYLC_DIR/bin:$CYLC_DIR/scripts:$PATH

# export PYTHONPATH to cylc core source modules
PYTHONPATH=$CYLC_DIR/src:$CYLC_DIR/src/job-submission:$CYLC_DIR/src/task-types:$CYLC_DIR/src/lockserver:$PYTHONPATH

if [[ -n $CYLC_SYSTEM_DIR ]]; then
    # caller must be a cylc jobfile; add system-specific paths as well
    PATH=$CYLC_SYSTEM_DIR/scripts:$PATH
    PYTHON_PATH=$CYLC_SYSTEM_DIR:$PYTHONPATH
fi

export PATH
export PYTHONPATH
