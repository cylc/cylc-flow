#!/usr/bin/env bash
set -eu

counter=1

while [ $counter -le 10 ]; do
    newrand=$(( (RANDOM % 40) + 1 ));
    echo "$newrand" >> report.txt;
    counter=$(( counter + 1 ));
done
