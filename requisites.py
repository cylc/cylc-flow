""" 
A class that holds a list of prerequisites (usually input filenames) or
postrequisites (usually output filenames), each of which is in a state of
"satisfied" or "not satisfied".  Each requisite starts out in a "not
satisfied" state.

E.g. prerequisites for modelx could include "filename_<reference_time>.foo" (a
postprequisite of modely), and "modelz postprocessing finished" (a
postrequisite of modelz.  
"""

class requisites:

	def __init__( self, reqs ):
		self.satisfied = {}
		for req in reqs:
			self.satisfied[req] = False

	def all_satisfied( self ):
		if False in self.satisfied.values(): 
			return False
		else:
			return True

	def is_satisfied( self, req ):
		if satisfied[ req ]:
			return True
		else:
			return False

	def set_satisfied( self, req ):
		self.satisfied[ req ] = True

	def set_all_satisfied( self ):
		for req in self.satisfied.keys():
			#print "setting " + req + " satisfied"
			self.satisfied[ req ] = True

	def satisfy_me( self, postreqs ):
		# can postreqs satisfy any of my prequisites?
		for prereq in self.satisfied.keys():
			# for each of my prerequisites
			if not self.satisfied[ prereq ]:
				# if not already satisfied
				for postreq in postreqs.satisfied.keys():
					if postreq == prereq and postreqs.satisfied[postreq]:
						self.set_satisfied( prereq )
		
	
