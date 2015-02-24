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

from parsec.validate import validator as vdr

"""
Legal items and validators for the parsec test config file.
"""

SPEC = {
        'title' : vdr( vtype="string" ),
        'single values' :
        {
            'integers' : { '__MANY__' : vdr( vtype="integer" ) },
            'booleans' : { '__MANY__' : vdr( vtype="boolean" ) },
            'floats'   : { '__MANY__' : vdr( vtype="float"   ) },
            'strings'  : { '__MANY__' : vdr( vtype="string"  ) },
            'strings with internal comments'  : { '__MANY__' : vdr( vtype="string"  ) },
            'multiline strings'  : { '__MANY__' : vdr( vtype="string"  ) },
            'multiline strings with internal comments'  : { '__MANY__' : vdr( vtype="string"  ) },
             },
        'list values' :
        {
            'string lists' :
            {
                '__MANY__'   : vdr( vtype="string_list"  ),
                'compulsory' : vdr( vtype="string_list", default=["jumped","over","the"], compulsory=True )
                },
            'integer lists' : { '__MANY__' : vdr( vtype="integer_list", allow_zeroes=False ) },
            'float lists'   : { '__MANY__' : vdr( vtype="float_list", allow_zeroes=False   ) },
            },
        }
