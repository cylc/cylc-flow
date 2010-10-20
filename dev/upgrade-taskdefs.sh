#!/bin/bash

for f in $@; do
    echo $f
    perl -pi -e 's/%CYCLES/%HOURS/g' $f
    perl -pi -e 's/%TASK/%COMMAND/g' $f
    perl -pi -e 's/%NAME/%TASK/g' $f
    perl -pi -e 's/%EXTRA_SCRIPTING/%SCRIPTING/g' $f
done

