#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import datetime
import os
import re
import sys
from shutil import copy as shcopy

from parsec.exceptions import ParsecError, IncludeFileNotFoundError


done = []
modtimes = {}
backups = {}
newfiles = []
flist = []

include_re = re.compile(r'\s*%include\s+([\'"]?)(.*?)([\'"]?)\s*$')


def inline(lines, dir_, filename, for_grep=False, for_edit=False, viewcfg=None,
           level=None):
    """Recursive inlining of parsec include-files"""

    global flist
    if level is None:
        # avoid being affected by multiple *different* calls to this function
        flist = [filename]
    else:
        flist.append(filename)
    single = False
    mark = False
    label = False
    if viewcfg:
        mark = viewcfg['mark']
        single = viewcfg['single']
        label = viewcfg['label']
    else:
        viewcfg = {}

    global done
    global modtimes

    outf = []
    initial_line_index = 0

    if level is None:
        level = ''
        if for_edit:
            m = re.match('^(#![jJ]inja2)', lines[0])
            if m:
                outf.append(m.groups()[0])
                initial_line_index = 1
            outf.append(
                """# !WARNING! CYLC EDIT INLINED (DO NOT MODIFY THIS LINE).
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

    for line in lines[initial_line_index:]:
        m = include_re.match(line)
        if m:
            q1, match, q2 = m.groups()
            if q1 and (q1 != q2):
                raise ParsecError("mismatched quotes: " + line)
            inc = os.path.join(dir_, match)
            if inc not in done:
                if single or for_edit:
                    done.append(inc)
                if for_edit:
                    backup(inc)
                    # store original modtime
                    modtimes[inc] = os.stat(inc).st_mtime
                if os.path.isfile(inc):
                    if for_grep or single or label or for_edit:
                        outf.append(
                            '#++++ START INLINED INCLUDE FILE ' + match + msg)
                    h = open(inc, 'r')
                    finc = [line.rstrip('\n') for line in h]
                    h.close()
                    # recursive inclusion
                    outf.extend(inline(
                        finc, dir_, inc, for_grep, for_edit, viewcfg, level))
                    if for_grep or single or label or for_edit:
                        outf.append(
                            '#++++ END INLINED INCLUDE FILE ' + match + msg)
                else:
                    flist.append(inc)
                    raise IncludeFileNotFoundError(flist)
            else:
                if not for_edit:
                    outf.append(level + line)
                else:
                    outf.append(line)
        else:
            # no match
            if not for_edit:
                outf.append(level + line)
            else:
                outf.append(line)
    return outf


def cleanup(suitedir):
    print('CLEANUP REQUESTED, deleting:')
    for root, _, files in os.walk(suitedir):
        for filename in files:
            if '.EDIT.' in filename:
                print(' + %s' % filename.replace(suitedir + '/', ''))
                os.unlink(os.path.join(root, filename))


def backup(src, tag=''):
    if not os.path.exists(src):
        raise SystemExit("File not found: " + src)
    bkp = src + tag + '.EDIT.' + datetime.datetime.now().isoformat()
    global backups
    shcopy(src, bkp)
    backups[src] = bkp


def split_file(dir_, lines, filename, recovery=False, level=None):
    global modtimes
    global newfiles

    if level is None:
        # config file itself
        level = ''
    else:
        level += ' > '
        # check mod time on the target file
        if not recovery:
            mtime = os.stat(filename).st_mtime
            if mtime != modtimes[filename]:
                # oops - original file has changed on disk since we started
                # editing
                filename += '.EDIT.NEW.' + datetime.datetime.now().isoformat()
        newfiles.append(filename)

    inclines = []
    fnew = open(filename, 'w')
    match_on = False
    for line in lines:
        if re.match('^# !WARNING!', line):
            continue
        if not match_on:
            m = re.match(
                r'^#\+\+\+\+ START INLINED INCLUDE FILE ' +
                r'([\w/.\-]+) \(DO NOT MODIFY THIS LINE!\)', line)
            if m:
                match_on = True
                inc_filename = m.groups()[0]
                inc_file = os.path.join(dir_, m.groups()[0])
                fnew.write('%include ' + inc_filename + '\n')
            else:
                fnew.write(line)
        elif match_on:
            # match on, go to end of the 'on' include-file
            m = re.match(
                r'^#\+\+\+\+ END INLINED INCLUDE FILE ' +
                inc_filename + r' \(DO NOT MODIFY THIS LINE!\)', line)
            if m:
                match_on = False
                # now split this lot, in case of nested inclusions
                split_file(dir_, inclines, inc_file, recovery, level)
                # now empty the inclines list ready for the next inclusion in
                # this file
                inclines = []
            else:
                inclines.append(line)
    if match_on:
        for line in inclines:
            fnew.write(line)
        print(file=sys.stderr)
        print((
            "ERROR: end-of-file reached while matching include-file",
            inc_filename + "."), file=sys.stderr)
        print((
            """This probably means you have corrupted the inlined file by
modifying one of the include-file boundary markers. Fix the backed-
up inlined file, copy it to the original filename and invoke another
inlined edit session split the file up again."""), file=sys.stderr)
        print(file=sys.stderr)
