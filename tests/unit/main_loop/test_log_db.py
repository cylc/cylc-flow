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
from textwrap import dedent

from cylc.flow.main_loop.log_db import _format


def test_format():
    """It should indent, fix case and strip comments in SQL statements."""
    assert _format('''
        select a, b, c, d, e, f, g
            from table_1 left join table_2
                where a = 1 and b = 2 and c = 3
                    # whatever
    ''') == dedent('''
        SELECT a,
               b,
               c,
               d,
               e,
               f,
               g
          FROM table_1
          LEFT JOIN table_2
         WHERE a = 1
           AND b = 2
           AND c = 3
    '''[1:])
