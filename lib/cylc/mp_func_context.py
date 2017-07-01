#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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

_FUNCS = {}
CYLC_MOD_LOC = 'cylc.xtriggers'
import os
SUITE_MOD_LOC = os.path.join('lib', 'python')


# TODO - MOVE THIS FUNCTION ELSEWHERE


def get_func(func_name):
    """Find and return a function from a module of the same name.

    Can be in MOD_LOC or anywhere in Python path.

    """
    if func_name in _FUNCS:
        return _FUNCS[func_name]
    for key in ["%s.%s" % (SUITE_MOD_LOC, func_name),
                "%s.%s" % (CYLC_MOD_LOC, func_name),
                func_name]:
        try:
            mod_by_name = __import__(key, fromlist=[key])
            _FUNCS[func_name] = getattr(mod_by_name, func_name)
            return _FUNCS[func_name]
        except ImportError as exc:
            # 1) 'cannot import...': module found but could not be imported.
            # 2) key == func_name: both location tried, module not found.
            if str(exc).startswith('cannot import') or key == func_name:
                raise
