#!/usr/bin/python

import Pyro.core
from system_status import system_status

# system state monitor class
state = system_status()

# pyro daemon
pyro_daemon = Pyro.core.Daemon()

# run modes
#run_mode = 0   # real models
#run_mode = 1    # dummy real time
run_mode = 2   # dummy catchup
