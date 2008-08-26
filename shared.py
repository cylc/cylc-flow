#!/usr/bin/python

import Pyro.core
from system_status import system_status

# system state monitor class
state = system_status()

# pyro daemon
pyro_daemon = Pyro.core.Daemon()
