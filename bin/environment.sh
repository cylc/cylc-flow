#!/bin/bash

# set PATH and PYTHONPATH for sequenz 

# CAN BE MODIFIED BY DEPLOYMENT SYSTEM AT INSTALL TIME
# ACCORDING TO WHERE SEQUENZ MODULES ARE INSTALLED TO.

# don't use $HOME here, as this may be source by task owners

# example system 
#export PATH=/test/ecoconnect_test/sequenz-dev/bin:/test/ecoconnect_test/sequenz-dev/example/tasks:$PATH
#export PYTHONPATH=/test/ecoconnect_test/sequenz-dev/src:/test/ecoconnect_test/sequenz-dev/example:$PYTHONPATH

# ecoconnect operational
#export PATH=/test/ecoconnect_test/sequenz-dev/bin:$PATH
#export PYTHONPATH=/test/ecoconnect_test/sequenz-dev/src:/test/ecoconnect_test/sequenz-dev/ecoconnect/operational:$PYTHONPATH# ecoconnect operational

# ecoconnect topnet test
export PATH=/test/ecoconnect_test/sequenz/bin:$PATH
export PYTHONPATH=/test/ecoconnect_test/sequenz/src:/test/ecoconnect_test/sequenz/ecoconnect/topnet-test:$PYTHONPATH
