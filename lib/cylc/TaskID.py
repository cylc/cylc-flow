#!/usr/bin/env python

import re
import datetime
from cylc.cycle_time import ct, CycleTimeError
from cylc.strftime import strftime

class TaskIDError( Exception ):
    def __str__( self ):
        return repr(self.msg)

class InvalidTaskIDError( TaskIDError ):
    def __init__( self, id ):
        self.msg = "ERROR, invalid task ID: " + id

class IllegalTaskNameError( TaskIDError ):
    def __init__( self, name ):
        self.msg = "ERROR, illegal task name: " + name

class InvalidCycleTimeError( TaskIDError ):
    def __init__( self, ctstr ):
        self.msg = "ERROR, illegal task cycle time: " + ctstr

class IllegalAsyncTagError( TaskIDError ):
    def __init__( self, atstr ):
        self.msg = "ERROR, illegal task tag: " + atstr

class TaskName(object):
    def __init__( self, name ):
        # alphanumeric and underscore allowed in task names
        if re.search( '[^\w]', name ):
            raise IllegalTaskNameError( name )
        self.name = name
    def getstr( self, formatted=False ):
        return self.name

class AsyncTag( object ):
    """Asynchronous task tag: int"""
    def __init__( self, tag_in ):
        tag = str(tag_in) # allow integer intput
        try:
            int(tag)
        except ValueError:
            raise IllegalAsyncTagError, tag
        self.tag = tag
    def getstr( self, formatted=False ):
        return self.tag
    def get( self, formatted=False ):
        # TO DO: get rid of this as we replace old ct() with new
        # CycleTime()
        return self.tag


class CycleTime( object ):
    """YYYY[MM[DD[HH[mm[ss]]]]]"""
    # template:
    YYYYMMDDHHmmss = '00010101000000'

    def __init__( self, ctin ):
        self.parse( ctin )

    def parse( self, strx ):
        n = len(strx)
        if n == 4 or n == 6 or n == 8 or n == 10 or n == 12 or n == 14:
            self.strvalue = strx + self.__class__.YYYYMMDDHHmmss[n:]
        else:
            raise InvalidCycleTimeError, strx

        #self.strvalue_Y2H = self.strvalue[0:10]

        self.year    = self.strvalue[ 0:4 ]
        self.month   = self.strvalue[ 4:6 ]
        self.day     = self.strvalue[ 6:8 ]
        self.hour    = self.strvalue[ 8:10]
        self.minute  = self.strvalue[10:12]
        self.seconds = self.strvalue[12:14]
        self.HHmmss  = self.strvalue[8:14 ]
        self.MMDDHHmmss  = self.strvalue[4:14 ]
 
        # convert to datetime as a validity check
        try:
            self.dtvalue = datetime.datetime( int(self.year), int(self.month),
                int(self.day), int(self.hour), int(self.minute),
                int(self.seconds))
        except ValueError,x:
            # returns sensible messages: "minute must be in 0..59"
            raise InvalidCycleTimeError( x.__str__() + ': ' + self.getstr(True) )

    def getstr( self, formatted=False ):
        if formatted:
            # YYYY/MM/DD HH:mm:ss
            return self.year + '/' + self.month + '/' + self.day + '|' + \
                    self.hour + ':' + self.minute + ':' + self.seconds
        else:
            #### TO DO: INTEGER CTIME COMPARISONS REQUIRE USE OF SAME NUMBER
            #### OF DIGITS EVERYWHERE
            #return self.strvalue
            return self.strvalue[0:10] # just YYYYMMDDHH for now

    def get_datetime( self ):
        return self.dtvalue

    def _str_from_datetime( self, dt ): 
        return strftime( dt, "%Y%m%d%H%M%S" )

    def increment( self, weeks=0, days=0, hours=0, minutes=0, seconds=0,
            microseconds=0, milliseconds=0 ): 
        # Can't increment by years or months easily - they vary in length.
        newdt = self.dtvalue + \
                datetime.timedelta( int(days), int(seconds),
                        int(microseconds), int(milliseconds), 
                        int(minutes), int(hours), int(weeks) )
        self.parse( self._str_from_datetime( newdt ))

    def decrement( self, weeks=0, days=0, hours=0, minutes=0, seconds=0,
            microseconds=0, milliseconds=0 ): 
        # Can't decrement by years or months easily - they vary in length.
        newdt = self.dtvalue - \
                datetime.timedelta( int(days), int(seconds),
                        int(microseconds), int(milliseconds), 
                        int(minutes), int(hours), int(weeks) )
        self.parse( self._str_from_datetime( newdt ))

    #def clone( self ):
    #    return ct( self.strvalue )

    def subtract( self, ct ):
        # subtract this ct from me, return a timedelta
        # (.days, .seconds, .microseconds)
         return self.dtvalue - ct.dtvalue

    def subtract_hrs( self, ct ):
        # subtract this ct from me, return hours
        delta = self.subtract(ct)
        return int( delta.days * 24 + delta.seconds / 3600 + delta.microseconds / ( 3600 * 1000000 ))

class TaskID(object):
    """A unique TaskID holds a task name and a tag, where the tag is an
    object holding either an integer for asynchronous tasks or a cycle
    time for cycling tasks. A task ID is initialized by string, either:
        1/ TaskID( "name.tag")
    or
        2/ TaskID( "name", "tag" )
    """

    delim = '.'

    def __init__( self, *args ):
        if len(args) == 1:
            id = args[0]
        elif len(args) == 2:
            id = args[0] + self.delim + str(args[1])
        else:
            raise InvalidTaskIDError, '"' + ','.join(args) + '"'
        try:
            name, tag = id.split( self.delim )
        except ValueError:
            raise InvalidTaskIDError, id
 
        self.name = TaskName(name)

        try:
            ct(tag)
        except CycleTimeError,x:
            # nope: is it an async integer tag?
            try:
                int( tag )
            except ValueError:
                # nope: not task ID, date time, or TAG
                raise InvalidTaskIDError, id
            else:
                self.asynchronous = True
                self.cycling = False
                self.tag = AsyncTag(tag)
        else:
            # cycling task
            self.cycling = True
            self.asynchronous = False
            self.tag = CycleTime(tag)

    def getstr( self, formatted=False ):
        if formatted:
            return self.name.getstr() + self.delim + self.tag.getstr(formatted)
        else:
            return self.name.getstr() + self.delim + self.tag.getstr()

    def split( self ):
        # return name and tag
        return ( self.name, self.tag )

    def splitstr( self ):
        # return name and tag as strings
        return ( self.name.getstr(), self.tag.getstr() )

if __name__ == "__main__":
    # UNIT TEST

    tasks = []

    # GOOD
    try:
        foo = TaskID( "foo.1") 
    except TaskIDError, x:
        print x
    else:
        tasks.append(foo)

    # GOOD
    try:
        bar = TaskID( "bar.2010080806")
    except TaskIDError, x:
        print x
    else:
        tasks.append(bar)

    # BAD
    try:
        baz = TaskID( "baz", "2010080808", 'WAZ' )
    except TaskIDError, x:
        print x
    else:
        tasks.append(baz)

    # BAD
    try:
        baz2 = TaskID( "b az2", "2010080808" )
    except TaskIDError, x:
        print x
    else:
        tasks.append(baz2)

    # BAD
    try:
        baz3 = TaskID( "baz3", "2010990808" )
    except TaskIDError, x:
        print x
    else:
        tasks.append(baz3)

    # PRINT THE GOOD ONES
    for task in tasks:
        print task.getstr(), task.getstr(formatted=True)

