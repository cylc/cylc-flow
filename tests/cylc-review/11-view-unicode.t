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
# Test for "cylc review", view file with unicode characters.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python3 -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

set_test_number 8
#-------------------------------------------------------------------------------
# Initialise, validate and run a suite for testing with
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
#!Jinja2
[cylc]
    UTC mode = True
    abort if any task fails = True
[scheduling]
    initial cycle point = 1999
    final cycle point = 2000
    [[dependencies]]
        [[[P1Y]]]
            graph = echo-euro
[runtime]
    [[echo-euro]]
        script = echo-euro >"$0.txt"
__SUITE_RC__

mkdir -p 'bin'
cat >'bin/echo-euro' <<'__BASH__'
#!/bin/bash
echo €
__BASH__
chmod +x 'bin/echo-euro'

TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME

cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null'
#-------------------------------------------------------------------------------
# Initialise WSGI application for the cylc review web service
TEST_NAME="${TEST_NAME_BASE}-ws-init"
cylc_ws_init 'cylc' 'review'
if [[ -z "${TEST_CYLC_WS_PORT}" ]]; then
    exit 1
fi

# Set up standard URL escaping of forward slashes in 'cylctb-' suite names.
ESC_SUITE_NAME="$(echo ${SUITE_NAME} | sed 's|/|%2F|g')"
#-------------------------------------------------------------------------------
# Tests of unicode output for standard '.txt' format
LOG_FILE='log/job/20000101T0000Z/echo-euro/01/job.txt'

TEST_NAME="${TEST_NAME_BASE}-200-curl-view-default"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=${LOG_FILE}"
cmp_ok "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" <<<'€'

TEST_NAME="${TEST_NAME_BASE}-200-curl-view-text"
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=${LOG_FILE}&mode=text"
cmp_ok "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" <<<'€'
#-------------------------------------------------------------------------------
# Test of unicode output for zipped 'tar.gz' format
TAR_FILE='job-19990101T0000Z.tar.gz'

TEST_NAME="${TEST_NAME_BASE}-200-curl-view-default-tar"
(cd "${SUITE_RUN_DIR}/log" && tar -czf "${TAR_FILE}" 'job/19990101T0000Z')
run_ok "${TEST_NAME}" curl \
    "${TEST_CYLC_WS_URL}/view/${USER}/${ESC_SUITE_NAME}?path=log/${TAR_FILE}&path_in_tar=job/19990101T0000Z/echo-euro/01/job.txt&mode=text"
cmp_ok "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" <<<'€'
#-------------------------------------------------------------------------------
# Tidy up - note suite trivial so stops early on by itself
purge_suite "${SUITE_NAME}"
cylc_ws_kill
exit
