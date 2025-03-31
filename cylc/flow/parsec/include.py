# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
import re
from typing import List

from cylc.flow.parsec.exceptions import (
    FileParseError, IncludeFileNotFoundError)


done: List[str] = []
flist: List[str] = []

include_re = re.compile(r'\s*%include\s+([\'"]?)(.*?)([\'"]?)\s*$')


def inline(lines, dir_, filename, for_grep=False, viewcfg=None, level=None):
    """Recursive inlining of parsec include-files"""
    if level is None:
        # avoid being affected by multiple *different* calls to this function
        flist[:] = [filename]
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

    outf = []
    initial_line_index = 0

    if level is None:
        level = ''
    elif mark:
        level += '!'

    msg = ''

    for line in lines[initial_line_index:]:
        m = include_re.match(line)
        if m:
            q1, match, q2 = m.groups()
            if q1 and (q1 != q2):
                raise FileParseError(
                    "mismatched quotes",
                    line=line,
                    fpath=filename,
                )
            inc = os.path.join(dir_, match)
            if inc not in done:
                if single:
                    done.append(inc)
                if not os.path.isfile(inc):
                    flist.append(inc)
                    raise IncludeFileNotFoundError(flist)
                if for_grep or single or label:
                    outf.append(
                        '#++++ START INLINED INCLUDE FILE ' + match + msg)
                with open(inc, 'r') as handle:
                    finc = [line.rstrip('\n') for line in handle]
                # recursive inclusion
                outf.extend(inline(
                    finc, dir_, inc, for_grep, viewcfg, level))
                if for_grep or single or label:
                    outf.append(
                        '#++++ END INLINED INCLUDE FILE ' + match + msg)

            else:
                outf.append(level + line)
        else:
            # no match
            outf.append(level + line)
    return outf
