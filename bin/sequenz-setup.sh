#!/bin/bash

# given a sequenz system definition directory:
#    system-name/config.py
#    system-name/taskdef/(task definition files)

# 1/ generate task class code for sequenz
# 2/ generate system environment script 
#    (which sets PATH and PYTHONPATH for the system)

set -e  # ABORT on error

[[ $# != 1 ]] && {
	echo "USAGE: $0 <system definition dir>"
	echo "should be run in sequenz repo top level"
	exit 1
}

[[ ! -f bin/sequenz.py ]] && {
	echo "RUN THIS IN SEQUENZ REPO TOP LEVEL"
	exit 1
}

SYSDIR=$1

cd $SYSDIR

echo "> generating task class code for sequenz: $SYSDIR/task_classes.py"
task_generator.py taskdef/*

# generate system environment script
echo "> generating environment script for this system: $SYSDIR/sequenz-env.sh"

echo > sequenz-env.sh <<EOF
#!/bin/bash

# set PATH and PYTHONPATH for running sequenz on a given set of tasks

# CAN BE MODIFIED BY DEPLOYMENT SYSTEM AT INSTALL TIME
# ACCORDING TO WHERE SEQUENZ MODULES ARE INSTALLED TO.

# don't use \$HOME here, as this may be source by task owners

export PATH=$PWD/bin:$PWD/$SYSDIR/tasks:$PATH
export PYTHONPATH=$PWD/src:$PWD/$SYSDIR:$PYTHONPATH
