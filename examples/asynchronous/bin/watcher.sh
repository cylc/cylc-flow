#!/bin/bash

COUNT=0
while true; do
    sleep 10
    cylc task message "SATID-${COUNT} is ready for processing."
    COUNT=$(( COUNT + 1 ))
done

cylc task finished
