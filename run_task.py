#!/usr/bin/python

import sys
import Pyro.core

from time import sleep
from reference_time import reference_time

assert( len( sys.argv) == 3)
    
[task_name, ref_time] = sys.argv[1:]
reference_time = reference_time( ref_time )

prefix = "   <" + task_name + " | " + reference_time.to_str() + ">: "

task = Pyro.core.getProxyForURI("PYRONAME://" + task_name + "_" + reference_time.to_str() )
# print  prefix + "vtask ID: " + task.identity()

while True:
    if task.is_complete():
        task.set_finished()
        break

    sleep(5)
    task.dummy_next_postrequisite()
