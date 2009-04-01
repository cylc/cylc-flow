#!/bin/bash

while true; do
    FOO="$(pyro-nsc listall)"
    clear
    echo "$FOO"
    sleep 2
done
