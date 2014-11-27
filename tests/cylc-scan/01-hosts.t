#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test cylc scan with multiple hosts
. "$(dirname "$0")/test_header"
HOSTS="$(cylc get-global-config '--item=[suite host scanning]hosts')"
if [[ -z "${HOSTS}" || "${HOSTS}" == 'localhost' ]]; then
    skip_all '"[suite host scanning]hosts" not defined with remote suite hosts'
fi
#-------------------------------------------------------------------------------
set_test_number "$(($(wc -w <<<"${HOSTS}") + 1))"
#-------------------------------------------------------------------------------
UUID="$(uuidgen)"
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
SCP='scp -oBatchMode=yes -oConnectTimeout=5'
set -e
for HOST in $(tr -d ',' <<<"${HOSTS}"); do
    if [[ "${HOST}" == 'localhost' ]]; then
        HOST_WORK_DIR="${PWD}"
        cp "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/suite.rc" .
    else
        HOST_WORK_DIR="$($SSH "${HOST}" 'mktemp -d')"
        $SCP "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/suite.rc" \
            "${HOST}:${HOST_WORK_DIR}"
    fi
    echo "${HOST}:${HOST_WORK_DIR}" >>'host-work-dirs.list'
    cylc register "--host=${HOST}" "${UUID}-${HOST}" "${HOST_WORK_DIR}" \
        1>/dev/null 2>&1
    mkdir -p "${HOME}/.cylc/${UUID}-${HOST}"
    if [[ "${HOST}" == 'localhost' ]]; then
        cp "${HOST_WORK_DIR}/passphrase" "${HOME}/.cylc/${UUID}-${HOST}"
    else
        $SCP "${HOST}:${HOST_WORK_DIR}/passphrase" \
            "${HOME}/.cylc/${UUID}-${HOST}"
    fi
    cylc run "--host=${HOST}" "${UUID}-${HOST}" 1>/dev/null 2>&1
done
run_ok "${TEST_NAME_BASE}" cylc scan
for ITEM in $(<'host-work-dirs.list'); do
    HOST="${ITEM%%:*}"
    HOST_WORK_DIR="${ITEM#*:}"
    grep_ok "^${UUID}-${HOST}" "${TEST_NAME_BASE}.stdout"
    cylc shutdown --now --max-polls=30 --interval=2 \
        "--host=${HOST}" "${UUID}-${HOST}" 1>/dev/null 2>&1
    if [[ "${HOST}" != 'localhost' ]]; then
        $SSH "${HOST}" "rm -fr '${HOST_WORK_DIR}' 'cylc-run/${UUID}-${HOST}'"
    else
        rm -fr "$(cylc get-global-config '--print-run-dir')/${UUID}-${HOST}"
    fi
    rm -fr "${HOME}/.cylc/${UUID}-${HOST}"
done
#-------------------------------------------------------------------------------
exit
