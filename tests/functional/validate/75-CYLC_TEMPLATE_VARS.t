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
# Test CYLC_TEMPLATE_VARS exported.

. "$(dirname "$0")/test_header"

set_test_number 3

cat > 'flow.cylc' <<__HEREDOC__
#!jinja2
{% from "cylc.flow" import LOG %} # cylc8
{% do LOG.info(CYLC_TEMPLATE_VARS) %}
[scheduling]
  initial cycle point = 2020
  [[graph]]
    R1 = another => one_thing

[runtime]
  [[root]]
    script = true
  [[another]]
  [[one_thing]]
__HEREDOC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate .
grep_ok "CYLC_TEMPLATE_VARS" "${TEST_NAME_BASE}-validate.stderr"
grep_ok "CYLC_VERSION" "${TEST_NAME_BASE}-validate.stderr"
