#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA
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
# Run tests to test HostAppointer class for selecting hosts.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 10

# No run hosts list
create_test_globalrc '' ''
run_ok "${TEST_NAME_BASE}-no-host-list" python3 - <<'__PYTHON__'
from cylc.flow.host_appointer import HostAppointer
assert HostAppointer().appoint_host() == 'localhost'
__PYTHON__

# Empty run hosts list
create_test_globalrc '' '
[suite servers]
    run hosts =
'
run_ok "${TEST_NAME_BASE}-empty-host-list" python3 - <<'__PYTHON__'
from cylc.flow.host_appointer import HostAppointer
assert HostAppointer().appoint_host() == 'localhost'
__PYTHON__

# Un-contactable host
create_test_globalrc '' "
[suite servers]
    run hosts = localhost, elephant
"
run_ok "${TEST_NAME_BASE}-uncontactable" python3 -c '
import sys
from cylc.flow.host_appointer import HostAppointer
appointer = HostAppointer()
for _ in range(10):
    if appointer.appoint_host() != "localhost":
        sys.exit(1)
'

# Invalid hostnames
create_test_globalrc '' "
[suite servers]
    run hosts = foo bar
[suite servers]
    condemned hosts = $(hostname)
"
run_fail "${TEST_NAME_BASE}-invalid" python3 -c '
from cylc.flow.host_appointer import HostAppointer
HostAppointer().appoint_host()
'
grep_ok 'list item "foo bar" cannot contain a space character' \
    "${TEST_NAME_BASE}-invalid.stderr"

create_test_globalrc '' ""  # reset global config before querying it
export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery]remote host with shared fs' \
    2>'/dev/null')
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip 5
    exit
fi

# Condemned host in host list
create_test_globalrc '' "
[suite servers]
    run hosts = localhost, ${CYLC_TEST_HOST}
[suite servers]
    condemned hosts = $(hostname)
"
run_ok "${TEST_NAME_BASE}-condemned-local" python3 -c '
import sys
from cylc.flow.host_appointer import HostAppointer
appointer = HostAppointer()
for _ in range(10):
    if appointer.appoint_host() == "localhost":
        sys.exit(1)
'

# Condemned host specified using alternative host name
create_test_globalrc '' "
[suite servers]
    run hosts = localhost, ${CYLC_TEST_HOST}
[suite servers]
    condemned hosts = $(hostname -f)
"
run_ok "${TEST_NAME_BASE}-condemned-variants" python3 -c '
import sys
from cylc.flow.host_appointer import HostAppointer
appointer = HostAppointer()
for _ in range(10):
    if appointer.appoint_host() == "localhost":
        sys.exit(1)
'

# All hosts are condemned
create_test_globalrc '' "
[suite servers]
    run hosts = localhost
[suite servers]
    condemned hosts = $(hostname)
"
run_fail "${TEST_NAME_BASE}-condemned-all" python3 -c '
from cylc.flow.host_appointer import HostAppointer
HostAppointer().appoint_host()
'

# Condemned hosts is ambiguous
create_test_globalrc '' "
[suite servers]
    run hosts = localhost, ${CYLC_TEST_HOST}
[suite servers]
    condemned hosts = localhost
"
run_fail "${TEST_NAME_BASE}-condemned-all" python3 -c '
from cylc.flow.host_appointer import HostAppointer
HostAppointer().appoint_host()
'
grep_ok 'ambiguous host "localhost"' "${TEST_NAME_BASE}-condemned-all.stderr"

exit
