#!/usr/bin/env python

import re

class triggerx(object):
    def __init__(self, name ):
        self.name = name
        self.msg = None
        self.type = 'succeeded'
        self.offset = None
        self.cycling = False
        self.async_oneoff = False
        self.async_repeating = False
        self.asyncid_pattern = None
        self.startup = False
        self.suicide = False
    def set_suicide( self, suicide ):
        self.suicide = suicide
    def set_startup( self ):
        self.startup = True
    def set_async_oneoff( self ):
        self.async_oneoff = True
    def set_async_repeating( self, pattern ):
        self.async_repeating = True
        self.asyncid_pattern = pattern
    def set_cycling( self ):
        self.cycling = True
    def set_special( self, msg ):
        # Replace <CYLC_TASK_CYCLE_TIME> with <TAG> in the internal output message
        self.msg = re.sub( 'CYLC_TASK_CYCLE_TIME', 'TAG', msg )
    def set_type( self, type ):
        # started, succeeded, failed
        self.type = type
    def set_offset( self, offset ):
        self.offset = offset
    def get( self, ctime, cycler ):
        if self.async_oneoff:
            preq = self.name + '%1' + ' ' + self.type
        elif self.async_repeating:
            preq = re.sub( '<ASYNCID>', '(' + self.asyncid_pattern + ')', self.msg )
        else:
            if self.msg:
                # TO DO: OFFSETS IN INTERNAL OUTPUTS
                preq =  self.msg
            else:
                if self.offset:
                    ctime = cycler.offset( ctime, self.offset )
                preq = self.name + '%' + ctime + ' ' + self.type
        # From old tclass_format_prerequisites
        preq = re.sub( '<TAG>', ctime, preq )
        return preq

