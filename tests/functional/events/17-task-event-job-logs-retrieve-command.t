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
# Test remote job logs retrieval custom command, requires compatible version of
# cylc on remote job host.
export REQUIRE_PLATFORM='loc:remote'
. "$(dirname "$0")/test_header"
set_test_number 3

create_test_global_config "" "
[platforms]
    [[${CYLC_TEST_PLATFORM}]]
        retrieve job logs = True
        retrieve job logs command = my-rsync
"
OPT_SET='-s GLOBALCFG=True'

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
mkdir -p "${RUN_DIR}/${WORKFLOW_NAME}/bin"
cat >"${RUN_DIR}/${WORKFLOW_NAME}/bin/my-rsync" <<'__BASH__'
#!/usr/bin/env bash
set -eu
echo "$@" >>"${CYLC_WORKFLOW_LOG_DIR}/my-rsync.log"
exec rsync -a "$@"
__BASH__
chmod +x "${RUN_DIR}/${WORKFLOW_NAME}/bin/my-rsync"

# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate ${OPT_SET} -s "PLATFORM='${CYLC_TEST_PLATFORM}'" "${WORKFLOW_NAME}"
# shellcheck disable=SC2086
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach ${OPT_SET} \
       -s "PLATFORM='${CYLC_TEST_PLATFORM}'" "${WORKFLOW_NAME}"

WORKFLOW_LOG_D="${RUN_DIR}/${WORKFLOW_NAME}/log"
sed 's/^.* -v //' "${WORKFLOW_LOG_D}/scheduler/my-rsync.log" >'my-rsync.log.edited'
sed -i -E 's/--max-size=[^ ]* //' 'my-rsync.log.edited'  # strip "retrieve job logs max size" arg
sort -u 'my-rsync.log.edited'  # strip out duplicates (can result from PBS log file spooling)

OPT_HEAD='--include=/1 --include=/1/t1'
OPT_TAIL='--exclude=/**'
ARGS="${CYLC_TEST_HOST}:cylc-run/${WORKFLOW_NAME}/log/job/ ${WORKFLOW_LOG_D}/job/"
cmp_ok 'my-rsync.log.edited' <<__LOG__
${OPT_HEAD} --include=/1/t1/01 --include=/1/t1/01/** ${OPT_TAIL} ${ARGS}
${OPT_HEAD} --include=/1/t1/02 --include=/1/t1/02/** ${OPT_TAIL} ${ARGS}
${OPT_HEAD} --include=/1/t1/03 --include=/1/t1/03/** ${OPT_TAIL} ${ARGS}
__LOG__

purge
exit
