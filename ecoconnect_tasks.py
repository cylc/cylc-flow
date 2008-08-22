#!/usr/bin/python

"""
Task classes for the Ecoconnect Controller.
See documentation in task.py
"""

from task import task
from reference_time import reference_time
from requisites import requisites

import os
import Pyro.core

class downloader( task ):
    "Met Office file downloader task class"

    def __init__( self, ref_time ):

        self.name = "downloader"

        self.prerequisites = requisites( [] )

        self.postrequisites = requisites( [ 
                 "10mwind_" + ref_time.to_str() + ".um",
                 "seaice_" + ref_time.to_str() + ".um",
                 "obstore_" + ref_time.to_str() + ".um",
                 "lbc_" + ref_time.to_str() + ".um",
                 "bgerr" + ref_time.to_str() + ".um" ])

        task.__init__( self, ref_time )

    
class nzlam12( task ):

    def __init__( self, ref_time ):

        self.name = "nzlam12"

        self.prerequisites = requisites( [ 
                 "obstore_" + ref_time.to_str() + ".um",
                 "lbc_" + ref_time.to_str() + ".um",
                 "bgerr" + ref_time.to_str() + ".um" ])

        self.postrequisites = requisites( [ 
                  "tn_" + ref_time.to_str() + ".nc",
                  "sls_" + ref_time.to_str() + ".nc",   
                  "met_" + ref_time.to_str() + ".nc" ])
        
        task.__init__( self, ref_time )
        

class nzwave12( task ):
    
    def __init__( self, ref_time ):

        self.name = "nzwave12"

        self.prerequisites = requisites( [ 
                 "sls_" + ref_time.to_str() + ".nc" ])

        self.postrequisites = requisites(["a", "b", "c"])
        
        task.__init__( self, ref_time )


class ricom( task ):

    
    def __init__( self, ref_time ):

        self.name = "ricom"

        self.prerequisites = requisites( [ 
                 "sls_" + ref_time.to_str() + ".nc" ])

        self.postrequisites = requisites(["d", "e", "f"])
        
        task.__init__( self, ref_time )


class topnet( task ):

    
    def __init__( self, ref_time ):

        self.name = "topnet"

        self.prerequisites = requisites( [ 
                 "tn_" + ref_time.to_str() + ".nc" ])

        self.postrequisites = requisites(["g", "h", "i"])
        
        task.__init__( self, ref_time )


class nwp_global( task ):

    def __init__( self, ref_time ):

        self.name = "nwp_global"

        self.prerequisites = requisites( [ 
                 "10mwind_" + ref_time.to_str() + ".um",
                 "seaice_" + ref_time.to_str() + ".um" ] )

        self.postrequisites = requisites([
                     "10mwind_" + ref_time.to_str() + ".nc",
                 "seaice_" + ref_time.to_str() + ".nc" ] )
    
        task.__init__( self, ref_time )
        

class globalwave120( task ):

    def __init__( self, ref_time ):

        self.name = "globalwave120"

        self.prerequisites = requisites( [ 
                 "10mwind_" + ref_time.to_str() + ".nc",
                 "seaice_" + ref_time.to_str() + ".nc" ] )

        self.postrequisites = requisites(["j", "k", "l"])
        
        task.__init__( self, ref_time )
        
