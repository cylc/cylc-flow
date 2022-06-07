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
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
while cylc ping "${SUITE_NAME}" 2>/dev/null; do
    sleep 1
done
sleep 8
suite_run_ok "${TEST_NAME_BASE}-restart" cylc restart "${SUITE_NAME}"
while cylc ping "${SUITE_NAME}" 2>/dev/null; do
    sleep 1
done
if [[ -e "${SUITE_RUN_DIR}/work/2/pub/test-succeeded" ]]; then
    ok "${TEST_NAME_BASE}-check"
else
    fail "${TEST_NAME_BASE}-check"
    echo 'OUT - Duplicated Entries:' >&2
    cat "${SUITE_RUN_DIR}/work/2/pub/out-duplication" >&2
    echo 'ERR - Duplicated Entries:' >&2
    cat "${SUITE_RUN_DIR}/work/2/pub/err-duplication" >&2
    echo 'LOG - Duplicated Entries:' >&2
    cat "${SUITE_RUN_DIR}/work/2/pub/log-duplication" >&2
fi

#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit