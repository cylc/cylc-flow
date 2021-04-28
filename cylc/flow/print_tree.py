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

import re

# Recursively pretty-print a nested dict as a tree

# Plain ASCII tree characters
a_hbar = '-'
a_vbar = '|'
a_tee = a_vbar + a_hbar
a_trm = '`' + a_hbar
a_tee_re = r'\|' + a_hbar

# Unicode box-printing characters
u_hbar = '\u2500'
u_vbar = '\u2502'
u_tee = '\u251C' + u_hbar
u_trm = '\u2514' + u_hbar


def get_tree(tree, padding, use_unicode=False, prefix='', labels=None,
             eq=False, sort=True):

    ret = []
    if use_unicode:
        vbar = u_vbar
        trm = u_trm
        tee = u_tee
        tee_re = tee
    else:
        vbar = a_vbar
        trm = a_trm
        tee = a_tee
        tee_re = a_tee_re

    keys = list(tree)
    if sort:
        keys.sort()
    # don't sort an ordered-dict tree!
    for item in keys:
        if item == keys[-1]:
            pprefix = prefix + ' ' + trm
        else:
            pprefix = prefix + ' ' + tee

        pp = pprefix
        pp = re.sub('^ (' + trm + '|' + tee_re + ')', '', pp)
        pp = re.sub(trm + ' ', '  ', pp)
        pp = re.sub(tee_re + ' ', vbar + ' ', pp)

        result = pp + item
        line = result + ' ' + padding[len(result):]
        if isinstance(tree[item], dict):
            ret.append(line)
            ret.extend(
                get_tree(
                    tree[item],
                    padding,
                    use_unicode,
                    pprefix,
                    labels,
                    eq
                )
            )
        else:
            if labels:
                if item in labels:
                    reason = labels[item][1]
                    ret.append(f'{line} ... {reason}')
                else:
                    ret.append(line)
            else:
                if eq:
                    joiner = '= '
                else:
                    joiner = ''
                ret.append(f'{line}{joiner}{tree[item]}')
    return ret


def print_tree(*args, **kwargs):
    print('\n'.join(get_tree(*args, **kwargs)))
