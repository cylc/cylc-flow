#!/bin/bashX # <-- prevent accidental non-dot-run!

# Source (dot-run) this script to configure your shell for THIS cylc.

# You must move to the top level of your cylc installation before
# sourcing this script OR first set $CYLC_DIR to that directory.

function cycl {
    echo "TYPO ALERT: it's 'cylc' NOT 'cycl'!"
    cylc $@
    return 0
}

if [[ -f bin/cylc ]]; then
    # we're in the top level of a cylc installation
    CYLC_DIR=$PWD

elif [[ ! -z $CYLC_DIR ]]; then
    if [[ ! -f $CYLC_DIR/bin/cylc ]]; then
        echo "ERROR: $CYLC_DIR is not a cylc installation"
        return 1
    fi
else
    echo "ERROR: source from top level cylc, or set CYLC_DIR"
    return 0
fi

echo "CONFIGURING THIS SHELL FOR $CYLC_DIR/bin/cylc"

PATH=$($CYLC_DIR/bin/_cylc-clean-path $PATH)
PYTHONPATH=$($CYLC_DIR/bin/_cylc-clean-path $PYTHONPATH)
export PATH=$CYLC_DIR/bin:$PATH
export PYTHONPATH=$CYLC_DIR/src:$PYTHONPATH
