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

import re, os, sys
from cylcconfigobj import ConfigObjError
import datetime
from shutil import copy

# To Do: the four file inclusion functions below are very similar and
# should be combined into one.

done = []
included = []
modtimes = {}
backups = {}
newfiles = []

def inline( lines, dir ):
    """Recursive inlining of suite.rc include-files"""
    outf = []
    for line in lines:
        m = re.match( '\s*%include\s+(.*)\s*$', line )
        if m:
            # include statement found
            match = m.groups()[0]
            # strip off possible quotes: %include "foo.inc"
            match = match.replace('"','')
            match = match.replace("'",'')
            inc = os.path.join( dir, match )
            if os.path.isfile(inc):
                #print "Inlining", inc
                h = open(inc, 'rb')
                inc = h.readlines()
                h.close()
                # recursive inclusion
                outf.extend( inline( inc, dir ))
            else:
                raise ConfigObjError, "ERROR, Include-file not found: " + inc
        else:
            # no match
            outf.append( line )
    return outf

def inline_for_viewing( dir, lines, mark=False, single=False, label=False, level=None ):
    """
    Recursive inlining of suite.rc include-files.
    This version marks ups the result for display by the cylc view command.
    """

    global done
    outf = []

    if level == None:
        level = ''
    else:
        if mark:
            level += '!'

    for line in lines:
        m = re.match( '\s*%include\s+(.*)\s*$', line )
        if m:
            match = m.groups()[0]
            # include statement found
            # strip off possible quotes: %include "foo.inc"
            match = match.replace('"','')
            match = match.replace("'",'')
            inc = os.path.join( dir, match )
            if inc not in done:
                if single:
                    done.append(inc)
                if os.path.isfile(inc):
                    print " + inlining", inc
                    if single or label:
                        outf.append('++++ START INLINED INCLUDE FILE ' + match + '\n' )
                    h = open(inc, 'rb')
                    inc = h.readlines()
                    h.close()
                    # recursive inclusion
                    outf.extend( inline_for_viewing( dir, inc, mark, single, label, level ))
                    if single or label:
                        outf.append('---- END INLINED INCLUDE FILE ' + match + '\n' )
                else:
                    raise SystemExit( "File not found: " + inc )
            else:
                outf.append(level + line)
        else:
            # no match
            outf.append(level + line)
    return outf

def inline_for_search( suitedir, inf ):
    """
    Recursive inlining of suite.rc include-files.
    This version marks ups the result for use by the cylc grep command.
    """

    outf = []
    for line in inf:
        m = re.match( '\s*%include\s+([\w/\.\-]+)\s*$', line )
        if m:
            match = m.groups()[0]
            inc = os.path.join( suitedir, match )
            if os.path.isfile(inc):
                #print "Inlining", inc
                outf.append('++++ START INLINED INCLUDE FILE ' + match + '\n')
                h = open(inc, 'rb')
                inc = h.readlines()
                h.close()
                # recursive inclusion
                outf.extend( inline_for_search( suitedir, inc ))
                outf.append('++++ END INLINED INCLUDE FILE ' + match + '\n')
            else:
                raise SystemExit( "File not found: " + inc )
        else:
            # no match
            outf.append( line )
    return outf

def inline_for_editing( dir, lines, level=None ):
    """
    Recursive inlining of suite.rc include-files.
    This version marks ups the result for display by the cylc edit command.
    """

    # using globals here for commonality across recursive calls:
    global included
    global modtimes
    outf = []
    if level == None:
        # suite.rc itself
        level = ''
        outf.append("""# !WARNING! CYLC EDIT INLINED (DO NOT MODIFY THIS LINE).
# !WARNING! This is an inlined suite.rc file; include-files are split
# !WARNING! out again on exiting the edit session.  If you are editing
# !WARNING! this file manually then a previous inlined session may have
# !WARNING! crashed; exit now and use 'cylc edit -i' to recover (this 
# !WARNING! will split the file up again on exiting).\n""")
    else:
        level += ' > '
    for line in lines:
        m = re.match( '\s*%include\s+(.*)\s*$', line )
        if m:
            match = m.groups()[0]
            # include statement found
            # strip off possible quotes: %include "foo.inc"
            match = match.replace('"','')
            match = match.replace("'",'')
            inc = os.path.join( dir, match )
            if inc not in included:
                # new include file detected
                # back up the original
                included.append(inc)
                backup( inc )
                # store original modtime
                modtimes[inc] = os.stat( inc ).st_mtime
                if os.path.isfile(inc):
                    #print " + inlining", inc
                    outf.append('#++++ START INLINED INCLUDE FILE ' + match  + ' (DO NOT MODIFY THIS LINE!)\n')
                    h = open(inc, 'rb')
                    inc = h.readlines()
                    h.close()
                    # recursive inclusion
                    outf.extend( inline_for_editing( dir, inc, level ))
                    outf.append('#---- END INLINED INCLUDE FILE ' + match  + ' (DO NOT MODIFY THIS LINE!)\n')
                else:
                    raise SystemExit( "ERROR, Include-file not found: " + inc )
            else:
                outf.append(line)
        else:
            # no match
            outf.append(line)
    return outf

def cleanup( suitedir ):
    print 'CLEANUP REQUESTED, deleting:'
    for root, dirs, files in os.walk( suitedir ):
        for file in files:
            if re.search( '\.EDIT\..*$', file ):
                print ' + ' + re.sub( suitedir + '/', '', file )
                os.unlink( os.path.join( root, file ))

def backup(src, tag='' ):
    if not os.path.exists(src):
        raise SystemExit( "File not found: " + src )
    bkp = src + tag + '.EDIT.' + datetime.datetime.now().isoformat()
    global backups
    copy( src, bkp )
    backups[ src ] = bkp


def split_file( dir, lines, file, recovery=False, level=None ):
    global modtimes
    global newfiles

    if level == None:
        # suite.rc itself
        level = ''
    else:
        level += ' > '
        # check mod time on the target file
        if not recovery:
            mtime = os.stat( file ).st_mtime
            if mtime != modtimes[file]:
                # oops - original file has changed on disk since we started editing
                f = re.sub( dir + '/', '', file )
                file = file + '.EDIT.NEW.' + datetime.datetime.now().isoformat()
        newfiles.append(file)

    inclines = []
    fnew = open( file, 'wb' )
    match_on = False
    for line in lines:
        if re.match( '^# !WARNING!', line ):
            continue
        if not match_on:
            m = re.match('^#\+\+\+\+ START INLINED INCLUDE FILE ([\w\/\.\-]+)', line )
            if m:
                match_on = True
                inc_filename = m.groups()[0]
                inc_file = os.path.join( dir, m.groups()[0] )
                fnew.write( '%include ' + inc_filename + '\n')
            else:
                fnew.write(line)
        elif match_on:
            # match on, go to end of the 'on' include-file
            m = re.match('^#\-\-\-\- END INLINED INCLUDE FILE ' + inc_filename, line )
            if m:
                match_on = False
                # now split this lot, in case of nested inclusions
                split_file( dir, inclines, inc_file, recovery, level )
                # now empty the inclines list ready for the next inclusion in this file
                inclines = []
            else:
                inclines.append(line)
    if match_on:
        for line in inclines:
            fnew.write( line )
        print >> sys.stderr 
        print >> sys.stderr, "ERROR: end-of-file reached while matching include-file", inc_filename + "."
        print >> sys.stderr, """This probably means you have corrupted the inlined file by
modifying one of the include-file boundary markers. Fix the backed-
up inlined suite.rc file, copy it to 'suite.rc' and invoke another
inlined edit session split the file up again."""
        print >> sys.stderr 

