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

# Test "cylc cat-log" open local logs in editor.

. "$(dirname $0)"/test_header

HOST="$( cylc get-global-config -i '[test battery]remote host' 2>'/dev/null')"
OWNER="$( cylc get-global-config -i '[test battery]remote owner' 2>'/dev/null')"
if [[ -z "${OWNER}${HOST}" ]]; then
    skip_all '"[test battery]remote host/owner": not defined'
fi

. "${TEST_SOURCE_DIR}"/editor/bin/run_tests.sh
export PATH="${TEST_SOURCE_DIR}/editor/bin/":"${PATH}"

install_suite "${TEST_NAME_BASE}" "editor"
run_tests "${HOST}" "${OWNER}"
purge_suite "${SUITE_NAME}"
