#!/bin/bash
# Script with cheat suggested in the tutorial to prevent
# flakyness caused by random.
sleep 10
RANDOM=$$  # Seed $RANDOM
DIE_1=$((RANDOM%6 + 1))
DIE_2=$((RANDOM%6 + 1))
echo "Rolled $DIE_1 and $DIE_2..."
if (($DIE_1 == $DIE_2)); then
    echo "doubles!"
elif (($CYLC_TASK_TRY_NUMBER >= 2)); then
    echo "look over there! ..."
    echo "doubles!"  # Cheat!
else
    exit 1
fi
