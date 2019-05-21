#!/usr/bin/env python2

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
"""Load custom variables for template processor."""


def load_template_vars(template_vars=None, template_vars_file=None):
    """Load template variables from key=value strings."""
    glbs = {'none': None, 'false': False, 'true': True}
    res = {}
    vars_list = []
    if template_vars_file:
        with open(template_vars_file) as vars_file:
            vars_from_file = vars_file.read()
        if template_vars_file.endswith('.py'):
            exec(vars_from_file, glbs, res)
        else:
            vars_list.extend(vars_from_file.split('\n'))
    if template_vars:
        try:
            exec('\n'.join(template_vars), glbs, res)
        except:
            vars_list.extend(template_vars)
    for line in vars_list:
        line = line.strip().split("#", 1)[0]
        if not line:
            continue
        key, val = line.split("=", 1)
        val = val.strip()
        res[key.strip()] = val.strip()
    res['SUITE_VARIABLES'] = dict(res)
    return res
