#!/usr/bin/env bash
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
# Test validation for some StandardError while doing Jinja2 processing.
. "$(dirname "$0")/test_header"

set_test_number 4

TEST_NAME="${TEST_NAME_BASE}-type-error"
cat >'suite.rc' <<'__SUITERC__'
#!jinja2

[scheduling]
    [[graph]]
        R1 = foo
{{ 1 / 'foo' }}
__SUITERC__
run_fail "${TEST_NAME}" cylc validate 'suite.rc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERROR__'
Jinja2Error: unsupported operand type(s) for /: 'int' and 'str'
Context lines:
    [[graph]]
        R1 = foo
{{ 1 / 'foo' }}	<-- TypeError
__ERROR__

TEST_NAME="${TEST_NAME}-value-error"
cat >'suite.rc' <<'__SUITERC__'
#!Jinja2
{% set foo = [1, 2] %}
{% set a, b, c = foo %}
__SUITERC__
run_fail "${TEST_NAME}" cylc validate 'suite.rc'
cmp_ok "${TEST_NAME}.stderr" <<'__ERROR__'
Jinja2Error: not enough values to unpack (expected 3, got 2)
Context lines:
#!Jinja2
{% set foo = [1, 2] %}
{% set a, b, c = foo %}	<-- ValueError
__ERROR__

exit
