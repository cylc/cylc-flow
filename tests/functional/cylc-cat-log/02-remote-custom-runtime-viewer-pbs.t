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
# Test "cylc cat-log" for viewing PBS runtime STDOUT/STDERR by a custom command
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"

RC_PREF='[test battery][batch systems][pbs]'
CYLC_TEST_HOST="$( \
    cylc get-global-config -i "${RC_PREF}host" 2>'/dev/null')"
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery][batch systems][pbs]host": not defined'
fi
ERR_VIEWER="$(cylc get-global-config -i "${RC_PREF}err viewer" 2>'/dev/null')"
OUT_VIEWER="$(cylc get-global-config -i "${RC_PREF}out viewer" 2>'/dev/null')"
if [[ -z "${ERR_VIEWER}" || -z "${OUT_VIEWER}" ]]; then
    skip_all '"[test battery][pbs]* viewer": not defined'
fi
CYLC_TEST_DIRECTIVES="$( \
    cylc get-global-config -i "${RC_PREF}[directives]" 2>'/dev/null')"
export CYLC_TEST_HOST CYLC_TEST_DIRECTIVES
set_test_number 2

create_test_globalrc "" "
[platforms]
    [[${CYLC_TEST_HOST}]]
        [[[batch systems]]]
            [[[[pbs]]]]
                err viewer = ${ERR_VIEWER}
                out viewer = ${OUT_VIEWER}"
reftest
purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
exit
