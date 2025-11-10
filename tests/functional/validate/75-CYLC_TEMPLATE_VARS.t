#!/usr/bin/env bash
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
#-------------------------------------------------------------------------------
# Test CYLC_TEMPLATE_VARS exported.

. "$(dirname "$0")/test_header"

set_test_number 2

cat > 'flow.cylc' <<__HEREDOC__
#!jinja2
[scheduling]
  initial cycle point = 2020
  [[graph]]
    R1 = foo

[runtime]
  [[foo]]
__HEREDOC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate . --debug
grep_ok "CYLC_TEMPLATE_VARS={'CYLC_VERSION': '.*', 'CYLC_TEMPLATE_VARS': {...}" \
    "${TEST_NAME_BASE}-validate.stderr"
