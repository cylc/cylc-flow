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
# Test that message triggers (custom outputs) are actioned immediately even if
# nothing else is happening at the time - GitHub #2548.

. "$(dirname "$0")/test_header"

set_test_number 4

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# The suite tests that two tasks suicide immediately on message triggers.
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" cylc run --no-detach "${SUITE_NAME}"

# Check that bar does nothing but suicide. 
TEST_NAME=${TEST_NAME_BASE}-cmp-bar
cylc cat-log "${SUITE_NAME}" | grep bar.1 | awk '{$1=""; print $0}' > bar.log
cmp_ok bar.log - << __END__
 INFO - [bar.1] -suiciding
__END__

# Check that baz does nothing but suicide. 
TEST_NAME=${TEST_NAME_BASE}-cmp-baz
cylc cat-log "${SUITE_NAME}" | grep baz.1 | awk '{$1=""; print $0}' > baz.log
cmp_ok baz.log - << __END__
 INFO - [baz.1] -suiciding
__END__

purge_suite "${SUITE_NAME}"
