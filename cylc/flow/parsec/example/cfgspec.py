# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Legal items and validators for the parsec test config file."""

from cylc.flow.parsec.validate import ParsecValidator as vdr


SPEC = {
    'title': [vdr.V_STRING],
    'single values': {
        'integers': {'__MANY__': [vdr.V_INTEGER]},
        'booleans': {'__MANY__': [vdr.V_BOOLEAN]},
        'floats': {'__MANY__': [vdr.V_FLOAT]},
        'strings': {'__MANY__': [vdr.V_STRING]},
        'strings with internal comments': {'__MANY__': [vdr.V_STRING]},
        'multiline strings': {'__MANY__': [vdr.V_STRING]},
        'multiline strings with internal comments': {
            '__MANY__': [vdr.V_STRING]}
    },
    'list values': {
        'string lists': {
            '__MANY__': [vdr.V_STRING_LIST],
            'compulsory': [vdr.V_STRING_LIST, ["jumped", "over", "the"]]
        },
        'integer lists': {'__MANY__': [vdr.V_INTEGER_LIST]},
        'float lists': {'__MANY__': [vdr.V_FLOAT_LIST]}
    }
}
