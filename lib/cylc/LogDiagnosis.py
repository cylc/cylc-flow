#!/usr/bin/env python

import os, re

class LogAnalyserError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class LogAnalyser( object ):
    def __init__( self, new_log, ref_log ):
        h = open( new_log, 'rb' )
        self.new_loglines = h.readlines()
        h.close()
        h = open( ref_log, 'rb' )
        self.ref_loglines = h.readlines()
        h.close()

    def get_triggered( self, lines ):
        res = []
        for line in lines:
            m = re.search( 'INFO - (\[.* -triggered off .*)$', line ) 
            if m:
                res.append(m.groups()[0])
        return res

    def verify_triggering( self ):
        new = self.get_triggered( self.new_loglines )
        ref = self.get_triggered( self.ref_loglines )

        if len(new) == 0:
            raise LogAnalyserError( "ERROR: new log contains no triggering info." )

        if len(ref) == 0:
            raise LogAnalyserError( "ERROR: reference log contains no triggering info." )

        new.sort()
        ref.sort()

        if new != ref:
            raise LogAnalyserError( "ERROR: suite triggering differs from the reference" )
        else:
            print "LogAnalyser: suite triggering agrees with the reference"

