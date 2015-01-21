#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, sys
import logging, logging.handlers
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from rolling_archive import rolling_archive

"""Configure suite stdout and stderr logs, as rolling archives, in a
sub-directory of the suite running directory. Can also be used to simply
get the configure log locations."""

class suite_output( object ):

    def __init__( self, suite ):

        sodir = GLOBAL_CFG.get_derived_host_item( suite, 'suite log directory' )
        self.opath = os.path.join( sodir, 'out' ) 
        self.epath = os.path.join( sodir, 'err' ) 

        # use same archive length as logging (TODO: document this)
        self.roll_at_startup = GLOBAL_CFG.get( ['suite logging','roll over at start-up'] )
        self.arclen = GLOBAL_CFG.get( ['suite logging','rolling archive length'] )

    def get_path( self, err=False ):
        if err:
            return self.epath
        else:
            return self.opath

    def redirect( self ):
        """redirect the standard file descriptors to suite log files."""

        self.roll()

        # record current standard file descriptors
        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr
        self.sys_stdin  = sys.stdin

        # redirect standard file descriptors
        # note that simply reassigning the sys streams is not sufficient
        # if we import modules that write to stdin and stdout from C
        # code - evidently the subprocess module is in this category!
        sout = file( self.opath, 'a+', 0 ) # 0 => unbuffered
        serr = file( self.epath, 'a+', 0 )
        dvnl = file( '/dev/null', 'r' )
        os.dup2( sout.fileno(), sys.stdout.fileno() )
        os.dup2( serr.fileno(), sys.stderr.fileno() )
        os.dup2( dvnl.fileno(), sys.stdin.fileno() )

    def restore( self ):
        # (not used)
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr
        sys.stdin  = self.sys_stdin
        print "\n Restored stdout and stderr to normal"

    def roll( self ):
        # roll the stdout and stderr log files
        oarchive = rolling_archive( self.opath, self.arclen, sep='.' )
        earchive = rolling_archive( self.epath, self.arclen, sep='.' )
        if self.roll_at_startup:
            oarchive.roll()
            earchive.roll()
