#!/bin/bash
# this file is part of the cylc suite engine.
# copyright (c) 2008-2018 niwa
# 
# this program is free software: you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation, either version 3 of the license, or
# (at your option) any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program.  if not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery]remote host with shared fs' \
    2>'/dev/null')
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery]remote host with shared fs": not defined'
fi
set_test_number 10
#-------------------------------------------------------------------------------
# test the failure recovery mechanism
BASE_GLOBALRC="
[cylc]
    health check interval = PT15S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT2M
        timeout = PT2M
[suite servers]
    run hosts = localhost, ${CYLC_TEST_HOST}"

TEST_NAME="${TEST_NAME_BASE}"
TEST_DIR="$HOME/cylc-run/" init_suite "${TEST_NAME}" <<< '
[scheduling]
    [[dependencies]]
        graph = foo
'
create_test_globalrc '' "${BASE_GLOBALRC}"
run_ok "${TEST_NAME}-suite-start" \
    cylc run "${SUITE_NAME}" --host=localhost --hold
poll ! test -f "${SUITE_RUN_DIR}/.service/contact"
sleep 1

# corrupt suite
rm "${SUITE_RUN_DIR}/suite.rc"

# condemn localhost
create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    condemned hosts = localhost
"

FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME}-shutdown" "${FILE}" 20 1 \
    'The Cylc suite host will soon become un-available' \
    'Suite shutting down - REQUEST(NOW-NOW)' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    'Could not restart suite will retry in 5s' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    'Could not restart suite will retry in 5s' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    'Could not restart suite will retry in 5s' \
    'Suite unable to automatically restart after 3 tries'

# stop suite - suite should already by stopped but just to be safe
cylc stop "${SUITE_NAME}" --kill 2>/dev/null
poll test -f "${SUITE_RUN_DIR}/.service/contact"
sleep 1
purge_suite "${SUITE_NAME}"

exit
