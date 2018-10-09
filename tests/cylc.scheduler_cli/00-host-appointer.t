#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
# Run unit tests to test HostAppointer class for selecting hosts.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7

run_ok "${TEST_NAME_BASE}" python -m 'cylc.scheduler_cli'

# No run hosts list
create_test_globalrc '' ''
run_ok "${TEST_NAME_BASE}-no-host-list" python - <<'__PYTHON__'
from cylc.scheduler_cli import HostAppointer
assert HostAppointer().appoint_host() == 'localhost'
__PYTHON__

# Empty run hosts list
create_test_globalrc '' '
[suite servers]
    run hosts =
'
run_ok "${TEST_NAME_BASE}-empty-host-list" python - <<'__PYTHON__'
from cylc.scheduler_cli import HostAppointer
assert HostAppointer().appoint_host() == 'localhost'
__PYTHON__

# Un-contactable host
create_test_globalrc '' "
[suite servers]
    run hosts = localhost, elephant
"
run_ok "${TEST_NAME_BASE}-uncontactable" python -c '
import sys
from cylc.scheduler_cli import HostAppointer
appointer = HostAppointer()
for _ in range(10):
    if appointer.appoint_host() != "localhost":
        sys.exit(1)
'

export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery]remote host with shared fs' \
    2>'/dev/null')
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip 3
    exit
fi

# Condemned host in host list
create_test_globalrc '' "
[suite servers]
    run hosts = localhost, ${CYLC_TEST_HOST}
[suite servers]
    condemned hosts = localhost
"
run_ok "${TEST_NAME_BASE}-condemned-local" python -c '
import sys
from cylc.scheduler_cli import HostAppointer
appointer = HostAppointer()
for _ in range(10):
    if appointer.appoint_host() == "localhost":
        sys.exit(1)
'

# Condemned host specified using altenative host name
create_test_globalrc '' "
[suite servers]
    run hosts = localhost, ${CYLC_TEST_HOST}
[suite servers]
    condemned hosts = $(hostname -f)
"
run_ok "${TEST_NAME_BASE}-condemned-variants" python -c '
import sys
from cylc.scheduler_cli import HostAppointer
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
    condemned hosts = localhost
"
run_fail "${TEST_NAME_BASE}-condemned-all" python -c '
from cylc.scheduler_cli import HostAppointer
HostAppointer().appoint_host()
'

exit
