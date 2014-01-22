#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
import datetime
from shutil import copy

class IncludeFileError( Exception ):
    """
    Attributes:
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

done = []
modtimes = {}
backups = {}
newfiles = []

include_re = re.compile( '\s*%include\s+([\'"]?)(.*?)([\'"]?)\s*$' )

def inline( lines, dir,
        for_grep=False, for_edit=False,
        viewcfg={}, level=None ):
    """Recursive inlining of parsec include-files"""

    single = False
    mark = False
    label = False
    if viewcfg:
        mark=viewcfg['mark']
        single=viewcfg['single']
        label=viewcfg['label']

    global done
    global modtimes

    outf = []

    if level == None:
        level = ''
        if for_edit:
            outf.append("""# !WARNING! CYLC EDIT INLINED (DO NOT MODIFY THIS LINE).
# !WARNING! This is an inlined parsec config file; include-files are split
# !WARNING! out again on exiting the edit session.  If you are editing
# !WARNING! this file manually then a previous inlined session may have
# !WARNING! crashed; exit now and use 'cylc edit -i' to recover (this 
# !WARNING! will split the file up again on exiting).""")

    else:
        if mark:
            level += '!'
        elif for_edit:
            level += ' > '

    if for_edit:
        msg = ' (DO NOT MODIFY THIS LINE!)'
    else:
        msg = ''

    for line in lines:
        m = include_re.match( line )
        if m:
            q1, match, q2 = m.groups()
            if q1 and ( q1 != q2 ):
                raise IncludeFileError( "ERROR, mismatched quotes: " + line )
            inc = os.path.join( dir, match )
            if inc not in done:
                if single or for_edit:
                    done.append(inc)
                if for_edit:
                    backup(inc)
                    # store original modtime
                    modtimes[inc] = os.stat( inc ).st_mtime
                if os.path.isfile(inc):
                    if for_grep or single or label or for_edit:
                        outf.append('#++++ START INLINED INCLUDE FILE ' + match + msg )
                    h = open(inc, 'rb')
                    inc = [ line.rstrip('\n') for line in h ]
                    h.close()
                    # recursive inclusion
                    outf.extend( inline( inc, dir, for_grep,for_edit,viewcfg,level ))
                    if for_grep or single or label or for_edit:
                        outf.append('#++++ END INLINED INCLUDE FILE ' + match + msg )
                else:
                    raise IncludeFileError( "ERROR, include-file not found: " + inc )
            else:
                if not for_edit:
                    outf.append( level + line )
                else:
                    outf.append( line )
        else:
            # no match
            if not for_edit:
                outf.append( level + line )
            else:
                outf.append( line )
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
        # config file itself
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
            m = re.match('^#\+\+\+\+ START INLINED INCLUDE FILE ([\w\/\.\-]+) \(DO NOT MODIFY THIS LINE!\)', line )
            if m:
                match_on = True
                inc_filename = m.groups()[0]
                inc_file = os.path.join( dir, m.groups()[0] )
                fnew.write( '%include ' + inc_filename + '\n')
            else:
                fnew.write(line)
        elif match_on:
            # match on, go to end of the 'on' include-file
            m = re.match('^#\+\+\+\+ END INLINED INCLUDE FILE ' + inc_filename + ' \(DO NOT MODIFY THIS LINE!\)', line )
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
up inlined file, copy it to the original filename and invoke another
inlined edit session split the file up again."""
        print >> sys.stderr 

