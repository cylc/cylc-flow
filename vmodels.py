#!/usr/bin/python

"""
Virtual model (vmodel) classes for the Ecoconnect Controller.

A vmodel represents a particular external model system for a single reference
time.  Each vmodel has certain prerequisites that must be satisfied before it
can launch its external model, and certain postrequisites that are created or
achieved as the model runs, and which may be prerequisites for other vmodels.
A vmodel must maintain an accurate representation of the model's state as it
follows through to the end of processing for its reference time.  

Vmodels communicate with each other in order to sort out inter-model
dependencies (i.e. match postrequisites with prerequisites).

In dummy mode, the vmodel just simulates its external model by satsifying
each of its postrequisites in turn once its (simulated) external model is
launched. 
"""

from ec_globals import dummy_mode
from reference_time import reference_time
from requisites import requisites


class vmodel:
	"ecoconnect vmodel base class"
	
	name = "vmodel base class"

	finished = False

	def __init__( self, ref_time ):
		self.ref_time = ref_time

	def run_if_satisfied( self ):
		if self.finished:
			#print self.name + ": (finished)"
			pass

		elif self.prerequisites.all_satisfied():
			self.start()
			self.run()
			self.finish()
		else:
			#print self.name + ": waiting"
			pass

	def start( self ):
		print self.name + ": STARTING for " + \
		self.ref_time.to_str()

	def run( self ):
		"override in derived classes, except in dummy mode"

		# print "     " + self.name + ": running for " + self.ref_time.to_str()
		pass

		if dummy_mode:
			self.postrequisites.set_all_satisfied()
		else:
			print "ERROR: no non-dummy run method defined"


	def finish( self ):
		#print "   " + self.name + ": FINISHED for " + self.ref_time.to_str()
		self.finished = True


	def get_satisfaction( self, other_models ):
		for other_model in other_models:
			self.prerequisites.satisfy_me( other_model.postrequisites )

	def report_state():
		pass


class downloader( vmodel ):
	"Met Office file downloader model class"

	name = "downloader"

	def __init__( self, ref_time ):
		self.prerequisites = requisites( [] )

		self.postrequisites = requisites( [ 
        		     "10mwind_" + ref_time.to_str() + ".um",
			     "seaice_" + ref_time.to_str() + ".um",
			     "obstore_" + ref_time.to_str() + ".um",
		             "lbc_" + ref_time.to_str() + ".um",
			     "bgerr" + ref_time.to_str() + ".um" ])

		vmodel.__init__( self, ref_time )

	
class nzlam12( vmodel ):
	"nzlam12 model class"

	name = "nzlam12"
	
	def __init__( self, ref_time ):
		self.prerequisites = requisites( [ 
			     "obstore_" + ref_time.to_str() + ".um",
		             "lbc_" + ref_time.to_str() + ".um",
			     "bgerr" + ref_time.to_str() + ".um" ])

		self.postrequisites = requisites( [ 
                              "tn_" + ref_time.to_str() + ".nc",
             		      "sls_" + ref_time.to_str() + ".nc", 	
	                      "met_" + ref_time.to_str() + ".nc" ])
		
		vmodel.__init__( self, ref_time )
		

class nzwave12( vmodel ):
	"nzwave12 model class"

	name = "nzwave12"
	
	def __init__( self, ref_time ):
		self.prerequisites = requisites( [ 
			     "sls_" + ref_time.to_str() + ".nc" ])

		self.postrequisites = requisites([])
		
		vmodel.__init__( self, ref_time )


class ricom( vmodel ):
	"ricom model class"

	name = "ricom"
	
	def __init__( self, ref_time ):
		self.prerequisites = requisites( [ 
			     "sls_" + ref_time.to_str() + ".nc" ])

		self.postrequisites = requisites([])
		
		vmodel.__init__( self, ref_time )

		

class topnet( vmodel ):
	"topnet model class"

	name = "topnet"
	
	def __init__( self, ref_time ):
		self.prerequisites = requisites( [ 
			     "tn_" + ref_time.to_str() + ".nc" ])

		self.postrequisites = requisites([])
		
		vmodel.__init__( self, ref_time )


class nwp_global( vmodel ):
	"nwp_global model class"

	name = "nwp_global"
	
	def __init__( self, ref_time ):
		self.prerequisites = requisites( [ 
			     "10mwind_" + ref_time.to_str() + ".um",
			     "seaice_" + ref_time.to_str() + ".um" ] )

		self.postrequisites = requisites([
		             "10mwind_" + ref_time.to_str() + ".nc",
			     "seaice_" + ref_time.to_str() + ".nc" ] )
	
		vmodel.__init__( self, ref_time )
		

class globalwave120( vmodel ):
	"globalwave120 model class"

	name = "globalwave120"
	
	def __init__( self, ref_time ):
		self.prerequisites = requisites( [ 
			     "10mwind_" + ref_time.to_str() + ".nc",
			     "seaice_" + ref_time.to_str() + ".nc" ] )

		self.postrequisites = requisites([])
		
		vmodel.__init__( self, ref_time )
		
