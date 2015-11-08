#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Test general task event handler + retry.
. "$(dirname "$0")/test_header"
HOST=$(cylc get-global-config -i '[test battery]remote host' 2>'/dev/null')
if [[ -z "${HOST}" ]]; then
    skip_all '"[test battery]remote host": not defined'
fi
set_test_number 4

mkdir 'conf'
cat >'conf/global.rc' <<__GLOBALCFG__
[hosts]
    [[${HOST}]]
        task event handler retry delays=3*PT1S
[task events]
    handlers=hello-event-handler '%(name)s' '%(event)s'
    handler events=succeeded, failed
__GLOBALCFG__

export CYLC_CONF_PATH="${PWD}/conf"
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
set -eu
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
${SSH} "${HOST}" \
    "mkdir -p .cylc/${SUITE_NAME}/ && cat >.cylc/${SUITE_NAME}/passphrase" \
    <"${TEST_DIR}/${SUITE_NAME}/passphrase"
set +eu

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate -s "HOST=${HOST}" -s 'GLOBALCFG=True' "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug -s "HOST=${HOST}" -s 'GLOBALCFG=True' \
    "${SUITE_NAME}"

SUITE_RUN_DIR="$(cylc get-global-config '--print-run-dir')/${SUITE_NAME}"
LOG="${SUITE_RUN_DIR}/log/job/1/t1/NN/job-activity.log"
sed "/(('event-handler-00', 'succeeded'), 1)/!d; s/^.* \[/[/" "${LOG}" \
    >'edited-job-activity.log'
cmp_ok 'edited-job-activity.log' <<'__LOG__'
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler 't1' 'succeeded'
[(('event-handler-00', 'succeeded'), 1) ret_code] 1
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler 't1' 'succeeded'
[(('event-handler-00', 'succeeded'), 1) ret_code] 1
[(('event-handler-00', 'succeeded'), 1) cmd] hello-event-handler 't1' 'succeeded'
[(('event-handler-00', 'succeeded'), 1) ret_code] 0
[(('event-handler-00', 'succeeded'), 1) out] hello
__LOG__

grep -F 'will run after' "${SUITE_RUN_DIR}/log/suite/log" \
    | cut -d' ' -f 4-11 >'edited-log'
cmp_ok 'edited-log' <<'__LOG__'
[t1.1] -(('event-handler-00', 'succeeded'), 1) will run after PT1S
[t2.1] -(('event-handler-00', 'succeeded'), 1) will run after P0Y
__LOG__


${SSH} "${HOST}" "rm -rf '.cylc/${SUITE_NAME}' 'cylc-run/${SUITE_NAME}'"
purge_suite "${SUITE_NAME}"
exit
