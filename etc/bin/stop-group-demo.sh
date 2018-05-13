#!/bin/bash

for S in $(cylc scan -n groups | awk '{print $1}'); do
  echo $S
  cylc stop $S
done
