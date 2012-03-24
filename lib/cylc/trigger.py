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
    def set_async_oneoff( self ):
        self.async_oneoff = True
    def set_async_repeating( self, pattern ):
        self.async_repeating = True
        self.asyncid_pattern = pattern
    def set_cycling( self ):
        self.cycling = True
    def set_special( self, msg ):
        self.msg = msg
    def set_type( self, type ):
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
        return preq

