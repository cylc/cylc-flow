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
# Run a workflow that was written directly in the cylc-run dir
# (rather than being installed by cylc install)
. "$(dirname "$0")/test_header"
set_test_number 1

# write a flow in the cylc-run dir
# (rather than using cylc-install to transfer it)
SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"
mkdir -p "${RUN_DIR}/${SUITE_NAME}"
cat > "${RUN_DIR}/${SUITE_NAME}/flow.cylc" <<__HERE__
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = foo
__HERE__

# ensure it can be run with no further meddling
suite_run_ok "${TEST_NAME_BASE}-run" cylc play "${SUITE_NAME}" --no-detach

purge
exit
