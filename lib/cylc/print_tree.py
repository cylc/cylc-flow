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

def print_tree( tree, padding, use_unicode=False, prefix='', labels=None ):
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
    keys.sort()
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
            print_tree( tree[item], padding, use_unicode, pprefix, labels )
        else:
            if labels:
                if item in labels:
                    tf, reason = labels[item]
                    print line, '...', reason
                else:
                    print line
            else:
                print line + str( tree[item] )

