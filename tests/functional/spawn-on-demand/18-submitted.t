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

# Test the submitted and submit-failed triggers work correctly.
#
# The :submitted output should be considered required unless explicitly stated
# otherwise.
# See:
# * https://github.com/cylc/cylc-flow/pull/5755
# * https://github.com/cylc/cylc-admin/blob/master/docs/proposal-new-output-syntax.md#output-syntax

. "$(dirname "$0")/test_header"
set_test_number 5

# define a broken platform which will always result in submission failures
create_test_global_config '' '
[platforms]
    [[broken]]
        hosts = no-such-host
'

install_and_validate
reftest_run

for number in 1 2 3; do
    grep_workflow_log_ok \
        "${TEST_NAME_BASE}-a${number}" \
        "${number}/a${number}.* did not complete the required outputs:"
done

purge
exit
