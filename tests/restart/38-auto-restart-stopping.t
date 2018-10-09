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
set_test_number 2
if ${CYLC_TEST_DEBUG:-false}; then ERR=2; else ERR=1; fi
#-------------------------------------------------------------------------------
BASE_GLOBALRC="
[cylc]
    health check interval = PT1S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT1M
        timeout = PT1M
[suite servers]
    run hosts = localhost, ${CYLC_TEST_HOST}"

TEST_NAME="${TEST_NAME_BASE}"

init_suite "${TEST_NAME}" <<< '
[scheduling]
    [[dependencies]]
        graph = foo => bar
[runtime]
    [[foo]]
        script = cylc stop "${CYLC_SUITE_NAME}"; sleep 15
' # note change TEST_DIR to force local installation in suite run dir

create_test_globalrc '' "
${BASE_GLOBALRC}
"

run_ok "${TEST_NAME}-suite-start" cylc run "${SUITE_NAME}" --host=localhost
cylc suite-state "${SUITE_NAME}" --task='foo' --status='running' --point=1 \
    --interval=1 --max-polls=20 >& $ERR

# condemn localhost
create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    condemned hosts = localhost
"

# wait for suite to die of natural causes
poll test -f "${SUITE_RUN_DIR}/.service/contact"
grep_ok 'Suite shutting down - REQUEST(CLEAN)' \
    "$(cylc cat-log "${SUITE_NAME}" -m p)"

exit
