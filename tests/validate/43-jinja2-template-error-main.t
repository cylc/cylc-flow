#!/bin/bash
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
#-------------------------------------------------------------------------------
# Test validation for a filter Jinja2 error with no line number.
. "$(dirname "$0")/test_header"

set_test_number 2

cat >'suite.rc' <<'__SUITERC__'
#!jinja2
{% set foo = {} %}
[scheduling]
    [[dependencies]]
        graph = {{ foo|dictsort(by='by') }}
[runtime]
    [[foo]]
        script = sleep 1
__SUITERC__
run_fail "${TEST_NAME_BASE}" cylc validate 'suite.rc'
contains_ok "${TEST_NAME_BASE}.stderr" <<'__ERROR__'
Jinja2Error:
    raise FilterArgumentError('You can only sort by either "key" or "value"')
FilterArgumentError: You can only sort by either "key" or "value"
__ERROR__

exit
