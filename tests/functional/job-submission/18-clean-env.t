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

# Test that local jobs can be divorced from the scheduler environment.
. "$(dirname "$0")/test_header"

create_test_global_config "" "
[job submission environment]
   divorce from scheduler = True
   environment = BEEF
[platforms]
   [[localhost]]
      # required - or central cylc wrapper - if divorced from scheduler:
      cylc executable = $(which cylc)
"

set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# Export a variable and try to access from a task job.
export BEEF=wellington
export CHEESE=melted
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"
cylc cat-log "${SUITE_NAME}" foo.1 > job.out

grep_ok "BEEF wellington" job.out
grep_ok "CHEESE undefined" job.out

purge_suite "${SUITE_NAME}"
exit
