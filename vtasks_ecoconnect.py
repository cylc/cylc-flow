#!/usr/bin/python

"""
Virtual task classes for the Ecoconnect Controller.
See documentation in vtask-base.py
"""

from vtask_base import vtask
from reference_time import reference_time
from requisites import requisites

import os
import Pyro.core

class downloader( vtask ):
    "Met Office file downloader task class"

    name = "downloader"

    def __init__( self, ref_time ):
        self.prerequisites = requisites( [] )

        self.postrequisites = requisites( [ 
                 "10mwind_" + ref_time.to_str() + ".um",
                 "seaice_" + ref_time.to_str() + ".um",
                 "obstore_" + ref_time.to_str() + ".um",
                 "lbc_" + ref_time.to_str() + ".um",
                 "bgerr" + ref_time.to_str() + ".um" ])

        vtask.__init__( self, ref_time )

    
class nzlam12( vtask ):

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
        
        vtask.__init__( self, ref_time )
        

class nzwave12( vtask ):

    name = "nzwave12"
    
    def __init__( self, ref_time ):
        self.prerequisites = requisites( [ 
                 "sls_" + ref_time.to_str() + ".nc" ])

        self.postrequisites = requisites(["a", "b", "c"])
        
        vtask.__init__( self, ref_time )


class ricom( vtask ):

    name = "ricom"
    
    def __init__( self, ref_time ):
        self.prerequisites = requisites( [ 
                 "sls_" + ref_time.to_str() + ".nc" ])

        self.postrequisites = requisites(["d", "e", "f"])
        
        vtask.__init__( self, ref_time )

        

class topnet( vtask ):

    name = "topnet"
    
    def __init__( self, ref_time ):
        self.prerequisites = requisites( [ 
                 "tn_" + ref_time.to_str() + ".nc" ])

        self.postrequisites = requisites(["g", "h", "i"])
        
        vtask.__init__( self, ref_time )


class nwp_global( vtask ):

    name = "nwp_global"
    
    def __init__( self, ref_time ):
        self.prerequisites = requisites( [ 
                 "10mwind_" + ref_time.to_str() + ".um",
                 "seaice_" + ref_time.to_str() + ".um" ] )

        self.postrequisites = requisites([
                     "10mwind_" + ref_time.to_str() + ".nc",
                 "seaice_" + ref_time.to_str() + ".nc" ] )
    
        vtask.__init__( self, ref_time )
        

class globalwave120( vtask ):

    name = "globalwave120"
    
    def __init__( self, ref_time ):
        self.prerequisites = requisites( [ 
                 "10mwind_" + ref_time.to_str() + ".nc",
                 "seaice_" + ref_time.to_str() + ".nc" ] )

        self.postrequisites = requisites(["j", "k", "l"])
        
        vtask.__init__( self, ref_time )
        
