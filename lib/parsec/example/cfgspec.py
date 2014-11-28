#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
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

from validate import validator as vdr

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
