#!/usr/bin/env python

import os, re
import datetime

class LogAnalyserError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class LogSpec( object ):
    # indexing from zero:
    start_tag_line_no = 3
    stop_tag_line_no = 4

    def __init__( self, log ):
        self.lines = []
        h = open( log, 'rb' )
        for line in range(self.__class__.stop_tag_line_no + 1):
            self.lines.append( h.readline().strip())
        h.close()

    def get_start_tag( self ):
        m = re.search( 'Start tag: (.*)$', self.lines[self.__class__.start_tag_line_no])
        if m:
            tag = m.groups()[0]
            if tag == "None":
                return None
            else:
                return tag
        else:
            raise LogAnalyserError( "ERROR: logged start tag not found" )

    def get_stop_tag( self ):
        m = re.search( 'Stop tag: (.*)$', self.lines[self.__class__.stop_tag_line_no])
        if m:
            tag = m.groups()[0]
            if tag == "None":
                return None
            else:
                return tag
        else:
            raise LogAnalyserError( "ERROR: logged stop tag not found" )

    def get_run_length( self ):
        # This was to compute the run length for reference tests, to set
        # the suite timeout automatically to twice (say) the reference
        # run length. BUT it's not much use the appropriate test run
        # length depends on the suite run mode.

        # TO RESTORE, READ IN *THE WHOLE LOG FILE* IN INIT ABOVE AND
        # COMPLETE THE DIFFERENCE CALCULATION BELOW.
        raise LogAnalyserError( "ERROR: method not fully implemented!" )

        m = re.search( 'Suite starting at (.*)$', self.lines[0] )
        if m:
            t1 = m.groups()[0]
        else:
            raise LogAnalyserError( "ERROR: logged real start time not found" )
        m = re.search( 'Suite shutting down at (.*)$', self.lines[-1] )
        if m:
            t2 = m.groups()[0]
        else:
            raise LogAnalyserError( "ERROR: logged real stop time not found" )
        # compute and return difference ...
        
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
            raise LogAnalyserError( "ERROR: triggering is NOT consistent with the reference log" )
        else:
            print "LogAnalyser: triggering is consistent with the reference log"

