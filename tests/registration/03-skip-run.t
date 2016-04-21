#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
#------------------------------------------------------------------------------
# Test skip unregister if suite has a port file.

. "$(dirname "$0")/test_header"
set_test_number 6

CYLC_RUND="$(cylc get-global-config --print-run-dir)"

SUITED_1="$(mktemp -d --tmpdir="${CYLC_RUND}" 'ctb-registration-03-1XXXXXXXX')"
SUITED_2="$(mktemp -d --tmpdir="${CYLC_RUND}" 'ctb-registration-03-2XXXXXXXX')"
SUITED_R="$(mktemp -d --tmpdir="${CYLC_RUND}" 'ctb-registration-03-RXXXXXXXX')"

for SUITED in "${SUITED_1}" "${SUITED_2}" "${SUITED_R}"; do
    cat >"${SUITED}/suite.rc" <<'__SUITERC__'
[cylc]
    [[event hooks]]
        timeout = PT1M
        abort on timeout = True
[scheduling]
    [[dependencies]]
        graph = foo
[runtime]
    [[foo]]
        script = false
__SUITERC__
    cylc register "$(basename "${SUITED}")" "${SUITED}" 1>'/dev/null'
done

cylc run "$(basename "${SUITED_R}")" 1>'/dev/null'
sleep 1

# Unregister on its own
run_fail "${TEST_NAME_BASE}-1" cylc unregister "$(basename "${SUITED_R}")"
cmp_ok "${TEST_NAME_BASE}-1.stdout" <<'__OUT__'
0 suite(s) unregistered.
__OUT__
cmp_ok "${TEST_NAME_BASE}-1.stderr" <<__ERR__
SKIP UNREGISTER $(basename "${SUITED_R}"): port file exists
__ERR__
# Unregister with regular expression
run_fail "${TEST_NAME_BASE}-A" cylc unregister 'ctb-registration-03-.*'
cmp_ok "${TEST_NAME_BASE}-A.stdout" <<__OUT__
UNREGISTER $(basename "${SUITED_1}"):${SUITED_1}
UNREGISTER $(basename "${SUITED_2}"):${SUITED_2}
2 suite(s) unregistered.
__OUT__
cmp_ok "${TEST_NAME_BASE}-A.stderr" <<__ERR__
SKIP UNREGISTER $(basename "${SUITED_R}"): port file exists
__ERR__

cylc shutdown --now --max-polls=30 --interval=2 "$(basename "${SUITED_R}")" \
    1>'/dev/null'

rm -fr "${SUITED_1}"
rm -fr "${SUITED_2}"
purge_suite "$(basename "${SUITED_R}")"

exit
