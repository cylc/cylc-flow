#!/usr/bin/env python

import os, re
import datetime

class LogAnalyserError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class LogSpec( object ):
    """Get important information from an existing reference run log
    file, in order to do the same run for a reference test. Currently
    just gets the start and stop cycle times."""

    def __init__( self, log ):
        h = open( log, 'rb' )
        self.lines = h.readlines()
        h.close()

    def get_start_tag( self ):
        found = False
        for line in self.lines:
            m = re.search( 'Start tag: (.*)$',line)
            if m:
                found = True
                tag = m.groups()[0]
                if tag == "None":
                    tag = None
                break
        if found:
            return tag
        else:
            raise LogAnalyserError( "ERROR: logged start tag not found" )

    def get_stop_tag( self ):
        found = False
        for line in self.lines:
            m = re.search( 'Stop tag: (.*)$',line)
            if m:
                found = True
                tag = m.groups()[0]
                if tag == "None":
                    return None
                break
        if found:
            return tag
        else:
            raise LogAnalyserError( "ERROR: logged stop tag not found" )

class LogAnalyser( object ):
    """Compare an existing reference log with the log from a new
    reference test run. Currently just compares triggering info."""

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

