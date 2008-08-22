#!/usr/bin/python

import Pyro.core
import status

# system state monitor class
state = status.status()

# pyro daemon
pyro_daemon = Pyro.core.Daemon()

# cycling period in hours
cycle_period = 6
