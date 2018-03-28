#!/bin/bash
#-------------------------------------------------------------------------------
# (C) British Crown Copyright 2012-8 Met Office.
#
# This file is part of Rose, a framework for meteorological suites.
#
# Rose is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Rose is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Rose. If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test for "rose bush", view file with unicode characters.
#-------------------------------------------------------------------------------
. "$(dirname "$0")/test_header"
if ! python -c 'import cherrypy' 2>'/dev/null'; then
    skip_all '"cherrypy" not installed'
fi

tests 7

ROSE_CONF_PATH= rose_ws_init 'rose' 'bush'
if [[ -z "${TEST_ROSE_WS_PORT}" ]]; then
    exit 1
fi

cat >'suite.rc' <<'__SUITE_RC__'
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

#-------------------------------------------------------------------------------
# Run a quick cylc suite
mkdir -p "${HOME}/cylc-run"
SUITE_DIR="$(mktemp -d --tmpdir="${HOME}/cylc-run" "rtb-rose-bush-11-XXXXXXXX")"
SUITE_NAME="$(basename "${SUITE_DIR}")"
cp -pr 'bin' 'suite.rc' "${SUITE_DIR}"
export CYLC_CONF_PATH=
cylc register "${SUITE_NAME}" "${SUITE_DIR}"
cylc run --no-detach --debug "${SUITE_NAME}" 2>'/dev/null' \
    || cat "${SUITE_DIR}/log/suite/err" >&2
#-------------------------------------------------------------------------------
LOG_FILE='log/job/20000101T0000Z/echo-euro/01/job.txt'

TEST_KEY="${TEST_KEY_BASE}-200-curl-view-default"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/view/${USER}/${SUITE_NAME}?path=${LOG_FILE}"
file_cmp "${TEST_KEY}.out" "${TEST_KEY}.out" <<<'€'

TEST_KEY="${TEST_KEY_BASE}-200-curl-view-text"
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/view/${USER}/${SUITE_NAME}?path=${LOG_FILE}&mode=text"
file_cmp "${TEST_KEY}.out" "${TEST_KEY}.out" <<<'€'
#-------------------------------------------------------------------------------
# Tar
TEST_KEY="${TEST_KEY_BASE}-200-curl-view-default-tar"
TAR_FILE='job-19990101T0000Z.tar.gz'
(cd "${SUITE_DIR}/log" && tar -czf "${TAR_FILE}" 'job/19990101T0000Z')
run_pass "${TEST_KEY}" curl \
    "${TEST_ROSE_WS_URL}/view/${USER}/${SUITE_NAME}?path=log/${TAR_FILE}&path_in_tar=job/19990101T0000Z/echo-euro/01/job.txt&mode=text"
file_cmp "${TEST_KEY}.out" "${TEST_KEY}.out" <<<'€'
#-------------------------------------------------------------------------------
# Tidy up
rose_ws_kill
rm -fr "${SUITE_DIR}" 2>'/dev/null'
exit 0
