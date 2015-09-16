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

import os
import sys
import re
import flags
from regpath import RegPath
from cylc.passphrase import passphrase
from cylc.suite_host import get_hostname
from cylc.owner import user

"""Simple suite name registration database."""

regdb_path = os.path.join( os.environ['HOME'], '.cylc', 'REGDB' )

class RegistrationError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class localdb(object):
    def __init__( self, file=None ):
        dbpath = file # (back compat)
        global regdb_path
        self.dbpath = dbpath or regdb_path
        # create initial database directory if necessary
        if not os.path.exists( self.dbpath ):
            try:
                os.makedirs( self.dbpath )
            except Exception,x:
                sys.exit( str(x) )

    def list_all_suites( self ):
        try:
            suites = os.listdir( self.dbpath )
        except Exception, x:
            sys.exit(str(x))
        return suites

    def register( self, name, dir ):
        name = RegPath(name).get()
        for suite in self.list_all_suites():
            if name == suite:
                raise RegistrationError, "ERROR: " + name + " is already registered."
            elif suite.startswith( name + RegPath.delimiter ):
                raise RegistrationError, "ERROR: " + name + " is a registered group."
            elif name.startswith( suite + RegPath.delimiter ):
                # suite starts with, to some level, an existing suite name
                raise RegistrationError, "ERROR: " + suite + " is a registered suite."
        dir = dir.rstrip( '/' )  # strip trailing '/'
        dir = re.sub( '^\./', '', dir ) # strip leading './'
        if not dir.startswith( '/' ):
            # On AIX on GPFS os.path.abspath(dir) returns the path with
            # full 'fileset' prefix. Manual use of $PWD to absolutize a
            # relative path gives a cleaner result.
            dir = os.path.join( os.environ['PWD'], dir )
        title = self.get_suite_title(name, path=dir)
        title = title.split('\n')[0] # use the first of multiple lines
        print 'REGISTER', name + ':', dir
        with open( os.path.join( self.dbpath, name ), 'w' ) as file:
            file.write( 'path=' + dir + '\n' )
            file.write( 'title=' + title + '\n' )

        # create a new passphrase for the suite if necessary
        passphrase(name,user,get_hostname()).generate(dir)

    def get_suite_data( self, suite ):
        suite = RegPath(suite).get()
        fpath = os.path.join( self.dbpath, suite )
        if not os.path.isfile( fpath ):
            raise RegistrationError, "ERROR: Suite not found " + suite
        data = {}
        with open( fpath, 'r' ) as file:
            lines = file.readlines()
        count = 0
        for line in lines:
            count += 1
            line = line.rstrip()
            try:
                key,val = line.split('=')
            except ValueError:
                print >> sys.stderr, 'ERROR: failed to parse line ' + str(count) + ' from ' + fpath + ':'
                print >> sys.stderr, '  ', line
                continue
            data[key] = val
        if 'title' not in data or 'path' not in data:
            raise RegistrationError, 'ERROR, ' + suite + ' suite registration corrupted?: ' + fpath
        return data

    def get_suitedir( self, reg ):
        data = self.get_suite_data( reg )
        return data['path']

    def get_suiterc( self, reg ):
        data = self.get_suite_data( reg )
        return os.path.join( data['path'], 'suite.rc' )

    def get_list( self, regfilter=None ):
        # Return a filtered list of valid suite registrations.
        res = []
        for suite in self.list_all_suites():
            if regfilter:
                try:
                    if not re.search(regfilter, suite):
                        continue
                except:
                    raise RegistrationError, "ERROR, Invalid filter expression: " + regfilter
            try:
                data = self.get_suite_data(suite)
            except RegistrationError as exc:
                print >> sys.stderr, str(exc)
            else:
                dir, title = data['path'], data['title']
                res.append( [suite, dir, title] )
        return res

    def unregister( self, exp ):
        suitedirs = []
        for key in self.list_all_suites():
            if re.search( exp + '$', key ):
                try:
                    data = self.get_suite_data(key)
                except RegistrationError:
                    pass
                else:
                    dir = data['path']
                    for f in ['passphrase', 'suite.rc.processed']:
                        try:
                            os.unlink( os.path.join( dir, f ) )
                        except OSError:
                            pass
                    if dir not in suitedirs:
                        # (could be multiple registrations of the same suite).
                        suitedirs.append(dir)
                print 'UNREGISTER', key
                os.unlink( os.path.join( self.dbpath, key ) )
        return suitedirs

    def reregister( self, srce, targ ):
        targ = RegPath(targ).get()
        found = False
        for suite in self.list_all_suites():
            if suite == srce:
                # single suite
                newsuite = targ
                data = self.get_suite_data( suite )
                dir, title = data['path'], data['title']
                self.unregister( suite )
                self.register( targ, data['path'] )
                found = True
            elif suite.startswith( srce + RegPath.delimiter ):
                # group of suites
                data = self.get_suite_data( suite )
                dir, title = data['path'], data['title']
                newsuite = re.sub( '^' + srce, targ, suite )
                self.unregister( suite )
                self.register( newsuite, data['path'] )
                found = True
        if not found:
            raise RegistrationError, "ERROR, suite or group not found: " + srce

    def get_invalid( self ):
        invalid = []
        for reg in self.list_all_suites():
            try:
                data = self.get_suite_data(reg)
            except RegistrationError:
                invalid.append(reg)
            else:
                dir = data['path']
                rcfile = os.path.join(dir, 'suite.rc')
                if not os.path.isfile(rcfile):
                    invalid.append(reg)
        return invalid

    def get_suite_title( self, suite, path=None ):
        """Determine the (first line of) the suite title without a full
        file parse. Assumes the title is not in an include-file."""

        if not path:
            data = self.get_suite_data( suite )
            path = data['path']
        suiterc = os.path.join( path, 'suite.rc' )

        title = "No title provided"
        for line in open( suiterc, 'rb' ):
            if re.search( '^\s*\[', line ):
                # abort: title comes before first [section]
                break
            m = re.match( '^\s*title\s*=\s*(.*)\s*$', line )
            if m:
                line = m.groups()[0]
                title = line.strip('"\'')

        return title

    def refresh_suite_title( self, suite ):
        data = self.get_suite_data(suite)
        dir, title = data['path'], data['title']
        new_title = self.get_suite_title( suite )
        if title == new_title:
            if flags.verbose:
                print 'unchanged:', suite
            changed = False
        else:
            print 'RETITLED:', suite
            print '   old title:', title
            print '   new title:', new_title
            changed = True
            self.unregister( suite )
            self.register( suite, dir )
        return changed

    def get_rcfiles ( self, suite ):
        # return a list of all include-files used by this suite
        # TODO - this needs to be made recursive
        rcfiles = []
        data = self.get_suite_data(suite)
        dir = data['path']
        suiterc = os.path.join( dir, 'suite.rc' )
        rcfiles.append( suiterc )
        for line in open( suiterc, 'rb' ):
            m = re.match( '^\s*%include\s+([\/\w\-\.]+)', line )
            if m:
                rcfiles.append(os.path.join( dir, m.groups()[0]))
        return rcfiles
