#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# Test cylc scan with multiple hosts
CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
HOSTS="$( \
    cylc get-global-config '--item=[suite host scanning]hosts' 2>'/dev/null')"
if [[ -z "${HOSTS}" || "${HOSTS}" == 'localhost' ]]; then
    skip_all '"[suite host scanning]hosts" not defined with remote suite hosts'
fi
#-------------------------------------------------------------------------------
set_test_number "$(($(wc -w <<<"${HOSTS}") + 1))"
#-------------------------------------------------------------------------------
PREFIX="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
SCP='scp -oBatchMode=yes -oConnectTimeout=5'
set -e
for HOST in $(tr -d ',' <<<"${HOSTS}"); do
    if [[ "${HOST}" == 'localhost' ]]; then
        HOST_WORK_DIR="${PWD}"
        cp "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/suite.rc" .
        cylc register "${PREFIX}-${HOST}" "${HOST_WORK_DIR}" 1>/dev/null 2>&1
        cylc run "${PREFIX}-${HOST}" 1>/dev/null 2>&1
        RUND="$(cylc get-global-config '--print-run-dir')/${PREFIX}-${HOST}"
        poll '!' test -e "${RUND}/.service/contact"
    else
        HOST_WORK_DIR="$($SSH -n "${HOST}" 'mktemp -d')"
        $SCP "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/suite.rc" \
            "${HOST}:${HOST_WORK_DIR}"
        cylc register "--host=${HOST}" "${PREFIX}-${HOST}" "${HOST_WORK_DIR}" \
            1>/dev/null 2>&1
        mkdir -p "${HOME}/.cylc/auth/${USER}@${HOST}/${PREFIX}-${HOST}"
        ${SCP} -p \
            "${HOST}:cylc-run/${PREFIX}-${HOST}/.service/passphrase" \
            "${HOST}:cylc-run/${PREFIX}-${HOST}/.service/ssl.*" \
            "${HOME}/.cylc/auth/${USER}@${HOST}/${PREFIX}-${HOST}/"
        cylc run "--host=${HOST}" "${PREFIX}-${HOST}" 1>/dev/null 2>&1
        poll '!' ${SSH} -n "${HOST}" \
            "test -e 'cylc-run/${PREFIX}-${HOST}/.service/contact'"
    fi
    echo "${HOST}:${HOST_WORK_DIR}" >>'host-work-dirs.list'
done
# Wait a bit before scanning, to ensure suites have initialized.
sleep 5
run_ok "${TEST_NAME_BASE}" cylc scan --comms-timeout=5
for ITEM in $(<'host-work-dirs.list'); do
    HOST="${ITEM%%:*}"
    HOST_WORK_DIR="${ITEM#*:}"
    run_ok "${TEST_NAME_BASE}-grep-${HOST}" \
        grep -q "^${PREFIX}-${HOST}" "${TEST_NAME_BASE}.stdout"
    if [[ "${HOST}" == 'localhost' ]]; then
        cylc shutdown --now --max-polls=30 --interval=2 "${PREFIX}-${HOST}" \
            1>'/dev/null' 2>&1
        rm -fr "$(cylc get-global-config '--print-run-dir')/${PREFIX}-${HOST}"
    else
        cylc shutdown --now --max-polls=30 --interval=2 \
            "--host=${HOST}" "${PREFIX}-${HOST}"
        purge_suite_remote "${HOST}" "${PREFIX}-${HOST}"
        rm -fr "${HOME}/.cylc/auth/${USER}@${HOST}/${PREFIX}-${HOST}/"
        (cd "${HOME}/.cylc/auth/" \
            && rmdir -p "${USER}@${HOST}/$(dirname "${PREFIX}")" 2>'/dev/null' \
            || true)
    fi
done
rmdir "${HOME}/.cylc/auth/" 2>'/dev/null' || true
#-------------------------------------------------------------------------------
exit
