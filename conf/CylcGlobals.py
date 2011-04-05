#!/usr/bin/env python

"""
MODULE FOR GLOBAL (PER CYLC INSTALLATION) CONFIGURATION DATA
"""

# Pyro base port (the lowest allowed socket number)
pyro_base_port = 7766   # (7766 is the Pyro default)

# Pyro max number of ports starting from base port
pyro_port_range = 100 # (100 is the Pyro default)

