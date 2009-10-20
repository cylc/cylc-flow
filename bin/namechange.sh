#!/bin/bash

set -e

# a quick script to help out if I change the name of the system again.

FILES=$@
mkdir bkp

for FILE in $FILES; do
    echo $FILE ...

    if [[ -d $FILE ]]; then
        echo skipping directory $FILE
        continue
    fi

    [[ $FILE = *namechange.sh ]] && {
        echo 'SKIPPING SELF'
        continue
    }

    IN=cyclon
    OUT=cylon

    INBIG=$( echo $IN | tr 'a-z' 'A-Z' )
    OUTBIG=$( echo $OUT | tr 'a-z' 'A-Z' )

    echo ... backing up
    cp $FILE bkp/${FILE}.bkp

    echo ... substituting $IN for $OUT
    cat $FILE | sed -e "s/$IN/$OUT/g" > tmp
    mv tmp $FILE
    echo ... substituting $INBIG for $OUTBIG
    cat $FILE | sed -e "s/$INBIG/$OUTBIG/g" > tmp
    mv tmp $FILE

done
