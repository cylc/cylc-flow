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
set_test_number 3

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
exit
