#!/usr/bin/python

import sys
import Pyro.core

#from reference_time import reference_time

status = Pyro.core.getProxyForURI("PYRONAME://" + "system_status" )

status_list = status.report()
