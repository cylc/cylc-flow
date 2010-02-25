#!/bin/bash-nonexistent # <-- prevent accidental non-dot-run!

# Source (dot-run) this script to configure your shell for THIS cylc.
# . cylc-env.sh

# You must do this in the top level directory of THIS cylc installation
# (i.e. the directory in which this file resides).

# You only need to do this if your login scripts do not provide access
# to this particular cylc installation.

if [[ ! -f bin/cylc ]]; then
    echo "ERROR: you do not seem to be in the top level of a cylc installation"

else

    PATH=$(bin/_cylc-clean-path $PATH)
    PYTHONPATH=$(bin/_cylc-clean-path $PYTHONPATH)

    export PATH=$PWD/bin:$PATH
    export PYTHONPATH=$PWD/src:$PYTHONPATH

    echo "SHELL CONFIGURED FOR $(which cylc)"

fi
