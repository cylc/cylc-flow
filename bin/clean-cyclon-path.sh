#!/bin/bash

# Clean existing cyclon paths from a supplied PATH variable
# Enables reconfiguring cyclon to a different task system
# without logging out and in again.

[[ $# > 1 ]] && {
	# ok to call for empty variables
	echo "USAGE: $0 <PATH-variable>"
	exit 1
}

IN_PATH=$1
OUT_PATH=''

OIFS=$IFS
IFS=':'
for P in $IN_PATH; do
	if [[ $P !=  *cyclon* ]]; then
		OUT_PATH=${OUT_PATH}:$P
	fi
done
IFS=$OIFS

OUT_PATH=${OUT_PATH#:}
OUT_PATH=${OUT_PATH%:}

echo $OUT_PATH
