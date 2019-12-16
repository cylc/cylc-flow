#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test `cylc monitor` output.
# Effectively a visual test, convert the terminal output to HTML then
# compare it to known good output (KGO)
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# TODO: replace this with the resultant database file
TEST_NAME="${TEST_NAME_BASE}-run"
run_ok "${TEST_NAME}" \
    cylc run "${SUITE_NAME}" --no-detach

TEST_NAME="${TEST_NAME_BASE}-restart"
run_ok "${TEST_NAME}" \
    cylc restart "${SUITE_NAME}" --no-detach

TEST_NAME="${TEST_NAME_BASE}-monitor"
run_ok "${TEST_NAME}" \
    cylc monitor "${SUITE_NAME}" \
    --display=html \
    --v-term-size=80,200
snapshot="${TEST_NAME}.stdout"



exit

#if ${CYLC_TEST_DEBUG:-false}; then ERR=2; else ERR=1; fi

#snapshot="$(cylc cat-log "${SUITE_NAME}" monitor.2000 -f job-html -m p)"

KGO="$(dirname "${snapshot}")/kgo.html"
cp "$TEST_SOURCE_DIR/$TEST_NAME_BASE/monitor.html" "${KGO}"

# substitute out variable content
sed -i \
    -e 's/\(batchSysJobId *\)[0-9]*/\1<jobid>/' \
    -e 's/\(startedTime *\)[0-9TZ:+\-]*/\1<time>/' \
    -e "s/cylctb-[0-9TZ:+-]*/<suite>/" \
    "${snapshot}"

if diff "${snapshot}" "${KGO}"; then
    ok "${TEST_NAME_BASE}"
else
    echo "Snapshot differs from KGO, use a web browser to compare:" >&2
    echo "  result: '${snapshot}'" >&2
    echo "  kgo: '${KGO}'" >&2
    fail "${TEST_NAME_BASE}"
fi

exit
