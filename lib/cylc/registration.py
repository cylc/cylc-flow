#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

import os, sys, re
from regpath import RegPath

"""Simple suite name registration database."""

regdb_path = os.path.join( os.environ['HOME'], '.cylc', 'REGDB' )

class RegistrationError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class localdb(object):
    def __init__( self, file=None, verbose=False):
        dbpath = file # (back compat)
        global regdb_path
        self.dbpath = dbpath or regdb_path
        self.verbose = verbose
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
        try:
            title = self.get_suite_title( name, path=dir )
        except Exception, x:
            print >> sys.stderr, 'WARNING: an error occurred parsing the suite definition:\n  ', x
            print >> sys.stderr, "Registering the suite with temporary title 'SUITE PARSE ERROR'."
            print >> sys.stderr, "You can update the title later with 'cylc db refresh'.\n"
            title = "SUITE PARSE ERROR"
        
        title = title.split('\n')[0] # use the first of multiple lines
        print 'REGISTER', name + ':', dir
        with open( os.path.join( self.dbpath, name ), 'w' ) as file:
            file.write( 'path=' + dir + '\n' )
            file.write( 'title=' + title + '\n' )

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
        # Return a filtered list of registered suites
        res = []
        for suite in self.list_all_suites():
            if regfilter:
                try:
                    if not re.search(regfilter, suite):
                        continue
                except:
                    raise RegistrationError, "ERROR, Invalid filter expression: " + regfilter
            data = self.get_suite_data( suite )
            dir, title = data['path'], data['title']
            res.append( [suite, dir, title] )
        return res

    def unregister( self, exp ):
        suitedirs = []
        for key in self.list_all_suites():
            if re.search( exp + '$', key ):
                data = self.get_suite_data(key)
                dir = data['path'] 
                print 'UNREGISTER', key + ':', dir
                os.unlink( os.path.join( self.dbpath, key ) )
                if dir not in suitedirs:
                    # (could be multiple registrations of the same suite).
                    suitedirs.append(dir)
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
                self.register( targ, data['path'] )
                self.unregister( suite )
                found = True
            elif suite.startswith( srce + RegPath.delimiter ):
                # group of suites
                data = self.get_suite_data( suite )
                dir, title = data['path'], data['title']
                newsuite = re.sub( '^' + srce, targ, suite )
                self.register( newsuite, data['path'] )
                self.unregister( suite )
                found = True
        if not found:
            raise RegistrationError, "ERROR, suite or group not found: " + srce

    def get_invalid( self ):
        invalid = []
        for reg in self.list_all_suites():
            data = self.get_suite_data(reg)
            dir = data['path']
            rcfile = os.path.join( dir, 'suite.rc' )
            if not os.path.isfile( rcfile ): 
                invalid.append( reg )
        return invalid

    def get_suite_title( self, suite, path=None ):
        "Determine the suite title without a full file parse"
        if not path:
            data = self.get_suite_data( suite )
            path = data['path']
        suiterc = os.path.join( path, 'suite.rc' )

        title = ""
        found_start = False
        done = False
        for xline in open( suiterc, 'rb' ):
            if re.search( '^ *\[', xline ):
                # abort the search: title comes before first [section]
                break
            line = xline.strip()
            if not found_start:
                m = re.match( '^title\s*=\s*([\'\"]+)(.*)', line )
                if m:
                    found_start = True
                    # strip quotes
                    start_quotes, line = m.groups()
            if found_start:
                if line.endswith( start_quotes ):
                    # strip quotes
                    line = re.sub( start_quotes, '', line )
                    done = True
                if title:
                    # adding on a second line on
                    title += " "
                title += line
                if done:
                    break

        if not title:
            title = "No title provided"
        return title

    def refresh_suite_title( self, suite ):
        data = self.get_suite_data(suite)
        dir, title = data['path'], data['title']
        new_title = self.get_suite_title( suite )
        if title == new_title:
            #if self.verbose:
            print 'unchanged:', suite#, '->', title
            changed = False
        else:
            print 'RETITLED:', suite #, '->', new_title
            changed = True
            self.items[suite] = dir, new_title
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

