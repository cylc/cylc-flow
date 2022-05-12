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
# ensure parsec can pull out the Jinja2 error lines even when they are behind
# an include statement
. "$(dirname "$0")/test_header"
set_test_number 2

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_NAME="${TEST_NAME_BASE}-validate"
run_fail "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
cmp_ok_re "${TEST_NAME}.stderr" <<__HERE__
Jinja2Error: .* some error
File .*foo.cylc
  # line before error
  {{ raise\('some error'\) }}
  # line after error.*<-- Exception
File .*flow.cylc
  #!Jinja2
  
  # line before include
  {% include "foo.cylc" %}.*<-- Exception
__HERE__

purge
exit
