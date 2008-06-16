#!/usr/bin/python

from vmodels import *
from time import sleep
from reference_time import reference_time 
from ec_globals import dummy_mode

""" Ecoconnect Controller with Implicit Scheduling

This program creates and manages vmodel objects, which represent
external ecoconnect "models", can launch their external models when
certain prerequisite conditions are satisfied, and which update their
internal state to reflect the status of the external model. Vmodels
interact in order to satisfy each other's prerequisites, which may
include conditions such as: 
 * file foo_<reference_time>.nc completed 
 * task foo finished successfully"

This method works if objects are instantiated for multiple reference
times at once, but there seems to be little point in doing that, and it
could make reporting system status messier.

To do each reference time separately means that vmodels can't have
prerequisites that depend on previous cycles: We assume therefore that
each real model checks for these prerequisite files and cold starts if 
they are not satisfied.

# Model postprocessing tasks could be handled by separate vmodels if they need
# to have their own prerequisites (e.g. "don't start ricom postprocessing until
# after nztide postprocessing completes, even if ricom completes before nztide").
# Otherwise a hierarchy of prerequisites may be needed for postprocessing tasks
# handled within the uber-vmodels.
"""

# initial reference time
cycle_time = reference_time( 2008, 05, 31, 12 )
	
models = []
def create_models():
	del models[:]
	models.append( downloader( cycle_time ))
	models.append( topnet( cycle_time ))
	models.append( ricom( cycle_time ))
	models.append( nwp_global( cycle_time ))
	models.append( globalwave120( cycle_time ))
	models.append( nzwave12( cycle_time ))
	models.append( nzlam12( cycle_time ))

create_models()

while True:
	finished = []
	for model in models:
		model.get_satisfaction( models )
		model.run_if_satisfied()
		finished.append( model.finished )

	print ""
	if not False in finished:
		print "all finished for " + cycle_time.to_str()
		cycle_time.increment()
		print "NEW REFERENCE TIME: " + cycle_time.to_str()
		print ""
		create_models()

	sleep(5)

