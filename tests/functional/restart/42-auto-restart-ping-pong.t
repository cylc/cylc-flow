#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
# Play a game of Cylc workflow ping pong bouncing a workflow back and forth between
# two servers by condemning them in turn in order to see if anything breaks
# Ensure that event handlers are not run on restart.
export REQUIRE_PLATFORM='loc:remote fs:shared runner:background'
. "$(dirname "$0")/test_header"
export CLOWNS="${CYLC_TEST_HOST}"
export JOKERS="${HOSTNAME}"

BASE_GLOBAL_CONFIG='
[scheduler]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT5S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT2M
        timeout = PT2M
'

init_workflow "${TEST_NAME_BASE}" <<< '
[scheduler]
    [[events]]
        handlers = handler.py
        handler events = startup
[scheduling]
    initial cycle point = 2000
    final cycle point = 9999  # test cylc/cylc-flow/issues/2799
    [[graph]]
        P1Y = foo[-P1Y] => foo
[runtime]
    [[foo]]
        script = sleep 5
'

mkdir "${WORKFLOW_RUN_DIR}/bin/"
cat <<__HERE__ > "${WORKFLOW_RUN_DIR}/bin/handler.py"
#!/usr/bin/env python3
raise Exception('This handler is meant to fail')
__HERE__
chmod +x "${WORKFLOW_RUN_DIR}/bin/handler.py"

cd "${WORKFLOW_RUN_DIR}" || exit 1
stuck_in_the_middle() {
    # swap the condemned host forcing the workflow to jump ship
    local temp="${JOKERS}"
    JOKERS="${CLOWNS}"; CLOWNS="${temp}"
    create_test_global_config '' "
    ${BASE_GLOBAL_CONFIG}
    [scheduler]
        [[run hosts]]
            available = ${JOKERS}, ${CLOWNS}
            condemned = ${CLOWNS}
    "
}

kill_workflow() {
    cylc stop --now --now --max-polls=10 --interval=2 "${WORKFLOW_NAME}" 2>'/dev/null'
    purge
}

log_scan2() {
    NO_TESTS="$(( NO_TESTS - $# + 4 ))"
    if ! log_scan "$@"; then
        skip $NO_TESTS  # skip remaining tests
        kill_workflow
        exit 1
    fi
}

EARS=5  # number of times to bounce the workflow between hosts
NO_TESTS="$(( EARS * 6 + 2 ))"
set_test_number "${NO_TESTS}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

# run the workflow
stuck_in_the_middle
cylc play "${WORKFLOW_NAME}" --host="${JOKERS}" --abort-if-any-task-fails
poll_workflow_running
sleep 1

# get the log file
FILE=$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)

grep_ok 'Exception: This handler is meant to fail' "$FILE"
#-------------------------------------------------------------------------------
for ear in $(seq 1 "${EARS}"); do
    stuck_in_the_middle  # swap the condemned host

    # test the shutdown procedure
    log_scan2 "${TEST_NAME_BASE}-${ear}-stop" "${FILE}" 40 1 \
        'The Cylc workflow host will soon become un-available' \
        'Workflow shutting down - REQUEST(NOW-NOW)' \
        "Attempting to restart on \"${JOKERS}\"" \
        "Workflow now running on \"${JOKERS}\"" \

    poll_workflow_restart

    # test the restart procedure
    FILE=$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)
    log_scan2 "${TEST_NAME_BASE}-${ear}-restart" "${FILE}" 20 1 \
        "Scheduler: url=tcp://$(get_fqdn "${JOKERS}")"
    grep_fail 'Exception: This handler is meant to fail' "$FILE"
    sleep 2
done

kill_workflow

exit
