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


# Test parameter vars are not defined with user env GitHub #2225

. "$(dirname "$0")/test_header"

set_test_number 5

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-config"
run_ok "${TEST_NAME}" \
    cylc get-config -i "[runtime][foo_t1_right]environment" "${SUITE_NAME}"
cmp_ok "${TEST_NAME}.stdout" - <<__END__
PARAM1 = \$CYLC_TASK_PARAM_t
PARAM2 = \$CYLC_TASK_PARAM_u
__END__
#------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-jobscript"
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" foo_t1_right.1
grep_ok 'export CYLC_TASK_PARAM_u="right"' "${TEST_NAME}.stdout"
grep_ok 'export CYLC_TASK_PARAM_t="1"' "${TEST_NAME}.stdout"
#------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
