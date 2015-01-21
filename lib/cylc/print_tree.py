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

import re

# Recursively pretty-print a nested dict as a tree

# Plain ASCII tree characters
a_hbar = '-'
a_vbar = '|'
a_tee = a_vbar + a_hbar
a_trm = '`' + a_hbar
a_tee_re = '\|' + a_hbar

# Unicode box-printing characters
u_hbar = u'\u2500'
u_vbar = u'\u2502'
u_tee = u'\u251C' + u_hbar
u_trm = u'\u2514' + u_hbar

def print_tree( tree, padding, use_unicode=False, prefix='', labels=None, eq=False ):
    if use_unicode:
        vbar = u_vbar
        trm = u_trm
        tee = u_tee
        tee_re= tee
    else:
        vbar = a_vbar
        trm = a_trm
        tee = a_tee
        tee_re = a_tee_re

    keys = tree.keys()
    # don't sort an ordered-dict tree!
    for item in keys:
        if item == keys[-1]:
            pprefix = prefix + ' ' + trm
        else:
            pprefix = prefix + ' ' + tee

        pp = pprefix
        pp = re.sub( '^ (' + trm + '|' + tee_re + ')', '', pp )
        pp = re.sub( trm + ' ', '  ', pp )
        pp = re.sub( tee_re + ' ', vbar + ' ', pp )

        result = pp + item
        line = result + ' ' + padding[ len(result): ]
        if isinstance( tree[item], dict ):
            print line
            print_tree( tree[item], padding, use_unicode, pprefix, labels, eq )
        else:
            if labels:
                if item in labels:
                    tf, reason = labels[item]
                    print line, '...', reason
                else:
                    print line
            else:
                if eq:
                    joiner = '= '
                else:
                    joiner = ''
                print line + joiner + str( tree[item] )
