#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import subprocess
import os, sys, re

# auto-replaced with version tag by new-release script:
cylc_version = "VERSION-TEMPLATE"

if cylc_version == "VERSION-" + "TEMPLATE": # (to avoid the replacement)
    # This must be a cylc repository, or a copy of the repository
    # source: use git to get a qualified most recent version tag.
    cwd = os.getcwd()
    os.chdir( os.environ['CYLC_DIR'] )
    try:
        p = subprocess.Popen( ['git', 'describe' ], stdout=subprocess.PIPE, stderr=subprocess.PIPE )
    except OSError,x:
        # git not found, 
        print sys.stderr, 'WARNING: failed to get repository pseudo version tag:'
    else:
        retcode = p.wait()
        if retcode != 0:
            # 'git describe' failed - this must be a copy of the
            # repository source but not a proper clone or a release.
            cylc_version = "(DEV)"
        else:
            # got a pseudo version number
            out, err = p.communicate()
            cylc_version = out.rstrip()
    os.chdir(cwd)

#_______________________________________________________________________
#-----------------CYLC-VERSION-COMPATIBILITY-MECHANISM------------------
# Any command that parses information from a suite.rc file, or runs a
# suite, or interacts with a running suite, should do the following:
#
#| from cylc.version import compat
#| # and after defining suite and suite.rc:
#| compat( suite, suiterc ).execute( sys.argv )
# 
# This will result in the command being executed using a different
# version of cylc than the version invoked, if the first line of the
# suite.rc file is either '#!cylc-x.y.z' or '#!/path/to/cylc-x.y.z'
# and the specified version is not the same as the invoked version.
#
# If the hash-bang line at the top of the suite.rc does not specify
# the full path to the required cylc installation, it will be computed
# by assuming parallel cylc installations: If the invoked command is in
# /foo/bar/baz/cylc-4.2.1/bin/cylc and you specify '#!cylc-4.3.2' then
# /foo/bar/baz/cylc-4.3.2/bin/cylc will be assumed.
#-----------------------------------------------------------------------

class compat( object ):
    def __init__( self, suite, suiterc ):
        self.suite = suite
        self.suiterc = suiterc
        self.messages = []

        try:
            f = open( suiterc, 'r' )
        except OSError, x:
            raise SystemExit(x)
        # read first line of the suite.rc file
        line0 = f.readline()
        line1 = f.readline()
        f.close()

        # location of the invoked cylc
        self.cylc_dir = os.environ['CYLC_DIR']

        # check for "#!cylc-x.y.z" or "#!/path/to/cylc-x.y.z" (not being
        # strict about the form of x.y.z because of unofficial releases):
        m = re.match( '^#!([\w/.-:]*cylc-.*)$', line0 )
        if m:
            # first line specifies cylc version
            z = m
        elif re.match( '^#![jJ]inja2\s*', line0 ):
            # First line specified Jinja2
            # Try second line for cylc version.
            z = re.match( '^#!([\w/.-:]*cylc-.*)$', line1 )
        else:
            z = None
        if z:
            self.required_cylc = z.groups()[0] # e.g. cylc-4.1.1 or /path/to/cylc-4.1.1
            self.required_version = re.sub( '^.*cylc-', '', self.required_cylc )  # e.g. 4.1.1
            if self.required_version != cylc_version:
                self.compatible = False
                self.messages.append( 'Cylc cross-version suite compatibility:' )
                self.messages.append( '  Invoked version: cylc-' + cylc_version + ' (' + self.cylc_dir + ')')
                self.messages.append( '  Suite requires:  ' + self.required_cylc )
            else:
                self.compatible = True
        else:
            # no version specified in suite, so assume compatible
            self.compatible = True
            self.required_version = None

    def get_version( self ):
        if self.required_version:
            return self.required_version
        else:
            return "version not specified"

    def execute( self, sysargv ):
        if self.compatible:
            # carry on as normal
            return

        # re-invoke the command (sysargv) using the required cylc version

        # determine location of the required cylc
        if os.path.isdir( self.required_cylc ):
            # full path specified by suite
            self.new_cylc_dir = self.required_cylc  
        else:
            # assume parallel installations at the same location
            self.new_cylc_dir = os.path.join( os.path.dirname( self.cylc_dir ), self.required_cylc )
            self.messages.append( 'Path not given, assuming parallel cylc installations' )

        self.messages.append( '=> Re-issuing command using ' + self.new_cylc_dir )

        # full path to new cylc command
        new_cylc = os.path.join( self.new_cylc_dir, 'bin', 'cylc')
        # construct the command to re-invoke
        command_path = sysargv[0]     # /path/to/this/cylc/bin/_validate
        command_name = os.path.basename( command_path ) # _validate
        # strip off initial '_' if there is one (may not be, e.g. gcylc SUITE) 
        command_name = re.sub( '^_', '', command_name )       # validate

        command = [new_cylc, command_name] + sysargv[1:] 

        maxlen = 0
        for item in self.messages:
            if len(item) > maxlen:
                maxlen = len(item)
        border = '-' * maxlen 
        print >> sys.stderr, border
        for item in self.messages:
            print >> sys.stderr, item
        print >> sys.stderr, border

        try:
            # THIS BLOCKS UNTIL THE COMMAND COMPLETES
            retcode = subprocess.call( command )
            sys.exit(retcode)
        except OSError, x:
            print >> sys.stderr, 'ERROR: Unable to invoke', new_cylc
            raise SystemExit( str(x) )

