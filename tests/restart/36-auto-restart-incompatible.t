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
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery]remote host with shared fs' \
    2>'/dev/null')
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery]remote host with shared fs": not defined'
fi
BASE_GLOBALRC="
[cylc]
    health check interval = PT5S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT2M
        timeout = PT2M
"
#-------------------------------------------------------------------------------
# Ensure suites don't attempt to stop-restart in cases where they shouldn't.
init_suite "${TEST_NAME_BASE}" <<< '
[scheduling]
    initial cycle point = 2000
    [[dependencies]]
        [[[P1D]]]
            graph = foo
'
POINT='99991230T2359Z'
OPTS=(
    '--no-auto-shutdown # can_auto_stop'
    "--until=${POINT} # final_point"
    '--no-detach # no_detach'
    "--hold-after=${POINT} # pool_hold_point"
    '--mode=dummy # run_mode'
    "cylc stop '${SUITE_NAME}' -w '${POINT}' # stop_clock_time"
    "cylc stop '${SUITE_NAME}' '${POINT}' # stop_point"
    "cylc stop '${SUITE_NAME}' 'foo.${POINT}' # stop_task"
)
set_test_number $(( ${#OPTS[@]} * 5 ))

for opt in "${OPTS[@]}"; do
    conf="$(sed 's/.*\# //' <<< "${opt}")"
    TEST_NAME="${TEST_NAME_BASE}-${conf}"
    if [[ ${opt:0:1} == '-' ]]; then
        clo="$(sed 's/\#.*//' <<< "${opt}")"
        cmd=true
    else
        clo=
        cmd="${opt}"
    fi

    create_test_globalrc '' "
    ${BASE_GLOBALRC}
    [suite servers]
        run hosts = localhost
    "

    cylc run "${SUITE_NAME}" --hold ${clo} --host=localhost >/dev/null 2>&1 &
    poll ! test -f "${SUITE_RUN_DIR}/.service/contact"
    run_ok "${TEST_NAME}-contact" cylc get-contact "${SUITE_NAME}"
    grep_ok "CYLC_SUITE_HOST=$(hostname -f)" "${TEST_NAME}-contact.stdout"

    eval "$cmd"
    sleep 2

    create_test_globalrc '' "
    ${BASE_GLOBALRC}
    [suite servers]
        run hosts = ${CYLC_TEST_HOST}
        condemned hosts = $(hostname)
    "

    log_scan "${TEST_NAME}-no-restart" \
        $(cylc cat-log "${SUITE_NAME}" -m p) 30 1 \
        'The Cylc suite host will soon become un-available' \
        'Suite cannot automatically restart' \
        "Incompatible configuration: \"${conf}\""

    cylc stop "${SUITE_NAME}" --now --now
    poll test -f "${SUITE_RUN_DIR}/.service/contact"
    sleep 1
done

purge_suite "${SUITE_NAME}"

exit
