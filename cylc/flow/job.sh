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

###############################################################################
# Bash functions for a cylc task job.
###############################################################################

###############################################################################
# The main function for a cylc task job.
cylc__job__main() {
    # Export CYLC_ suite and task environment variables
    cylc__job__inst__cylc_env
    # Turn on xtrace in debug mode
    if "${CYLC_DEBUG:-false}"; then
        if [[ -n "${BASH:-}" ]]; then
            PS4='+[\D{%Y%m%dT%H%M%S%z}]\u@\h '
            exec 19>>"${CYLC_SUITE_RUN_DIR}/log/job/${CYLC_TASK_JOB}/job.xtrace"
            export BASH_XTRACEFD=19
            >&2 echo "Sending DEBUG MODE xtrace to job.xtrace"
        fi
        set -x
    fi
    # Prelude
    typeset file_name=
    # conf/job-init-env.sh for back-compat pre 7.7.0.
    for file_name in \
        "${HOME}/.cylc/job-init-env.sh" \
        "${CYLC_DIR}/etc/job-init-env.sh" \
        "${CYLC_DIR}/conf/job-init-env.sh"
    do
        if [[ -f "${file_name}" ]]; then
            if "${CYLC_DEBUG:-false}"; then
                . "${file_name}"
            else
                . "${file_name}" 1>'/dev/null' 2>&1
            fi
            break
        fi
    done
    # Ensure that the "cylc" command is in PATH. It may not be set up correctly
    # in Prelude above, and also not inherited from the job submit environment.
    if ! command -v cylc 1>'/dev/null' 2>&1; then
        PATH="${CYLC_DIR}/bin:${PATH}"
    fi
    # Init-Script
    cylc__job__run_inst_func 'global_init_script'
    cylc__job__run_inst_func 'init_script'
    # Start error and vacation traps
    typeset signal_name=
    for signal_name in ${CYLC_FAIL_SIGNALS}; do
        # shellcheck disable=SC2064
        trap "cylc__job_err ${signal_name}" "${signal_name}"
    done
    for signal_name in ${CYLC_VACATION_SIGNALS:-}; do
        # shellcheck disable=SC2064
        trap "cylc__job_vacation ${signal_name}" "${signal_name}"
    done
    set -euo pipefail
    # Write task job self-identify
    USER="${USER:-$(whoami)}"
    typeset host="${HOSTNAME:-}"
    if [[ -z "${host}" ]]; then
        if [[ "$(uname)" == 'AIX' ]]; then
            # On AIX the hostname command has no '-f' option
            typeset host="$(hostname).$(namerslv -sn 2>'/dev/null' | awk '{print $2}')"
        else
            typeset host="$(hostname -f)"
        fi
    fi
    # Developer Note:
    # We were using a HERE document for writing info here until we notice that
    # Bash uses temporary files for HERE documents, which can be inefficient.
    echo "Suite    : ${CYLC_SUITE_NAME}"
    echo "Task Job : ${CYLC_TASK_JOB} (try ${CYLC_TASK_TRY_NUMBER})"
    echo "User@Host: ${USER}@${host}"
    echo
    # Derived environment variables
    export CYLC_SUITE_LOG_DIR="${CYLC_SUITE_RUN_DIR}/log/suite"
    CYLC_SUITE_WORK_DIR_ROOT="${CYLC_SUITE_WORK_DIR_ROOT:-${CYLC_SUITE_RUN_DIR}}"
    export CYLC_SUITE_SHARE_DIR="${CYLC_SUITE_WORK_DIR_ROOT}/share"
    export CYLC_SUITE_WORK_DIR="${CYLC_SUITE_WORK_DIR_ROOT}/work"
    CYLC_TASK_CYCLE_POINT="$(cut -d '/' -f 1 <<<"${CYLC_TASK_JOB}")"
    CYLC_TASK_NAME="$(cut -d '/' -f 2 <<<"${CYLC_TASK_JOB}")"
    export CYLC_TASK_NAME CYLC_TASK_CYCLE_POINT
    # The "10#" part ensures that the submit number is interpreted in base 10.
    # Otherwise, a zero padded number will be interpreted as an octal.
    export CYLC_TASK_SUBMIT_NUMBER=$((10#$(cut -d '/' -f 3 <<<"${CYLC_TASK_JOB}")))
    export CYLC_TASK_ID="${CYLC_TASK_NAME}.${CYLC_TASK_CYCLE_POINT}"
    export CYLC_TASK_LOG_DIR="${CYLC_SUITE_RUN_DIR}/log/job/${CYLC_TASK_JOB}"
    export CYLC_TASK_LOG_ROOT="${CYLC_TASK_LOG_DIR}/job"
    if [[ -n "${CYLC_TASK_WORK_DIR_BASE:-}" ]]; then
        # Note: value of CYLC_TASK_WORK_DIR_BASE may contain variable
        # substitution syntax including some of the derived variables above, so
        # it can only be derived at point of use.
        CYLC_TASK_WORK_DIR_BASE="$(eval echo "${CYLC_TASK_WORK_DIR_BASE}")"
    else
        CYLC_TASK_WORK_DIR_BASE="${CYLC_TASK_CYCLE_POINT}/${CYLC_TASK_NAME}"
    fi
    export CYLC_TASK_WORK_DIR="${CYLC_SUITE_WORK_DIR}/${CYLC_TASK_WORK_DIR_BASE}"
    typeset contact="${CYLC_SUITE_RUN_DIR}/.service/contact"
    if [[ -f "${contact}" ]]; then
        CYLC_SUITE_HOST="$(sed -n 's/^CYLC_SUITE_HOST=//p' "${contact}")"
        CYLC_SUITE_OWNER="$(sed -n 's/^CYLC_SUITE_OWNER=//p' "${contact}")"
        export CYLC_SUITE_HOST CYLC_SUITE_OWNER
    fi
    # DEPRECATED environment variables
    export CYLC_SUITE_SHARE_PATH="${CYLC_SUITE_SHARE_DIR}"
    export CYLC_SUITE_INITIAL_CYCLE_TIME="${CYLC_SUITE_INITIAL_CYCLE_POINT}"
    export CYLC_SUITE_FINAL_CYCLE_TIME="${CYLC_SUITE_FINAL_CYCLE_POINT}"
    export CYLC_TASK_CYCLE_TIME="${CYLC_TASK_CYCLE_POINT}"
    export CYLC_TASK_WORK_PATH="${CYLC_TASK_WORK_DIR}"
    # Env-Script
    cylc__job__run_inst_func 'env_script'
    # Send task started message
    cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" 'started' &
    CYLC_TASK_MESSAGE_STARTED_PID=$!
    # Access to the suite bin directory (installed run-dir first).
    export PATH="${CYLC_SUITE_RUN_DIR}/bin:${CYLC_SUITE_DEF_PATH}/bin:${PATH}"
    # Create share and work directories
    mkdir -p "${CYLC_SUITE_SHARE_DIR}" || true
    mkdir -p "$(dirname "${CYLC_TASK_WORK_DIR}")" || true
    mkdir -p "${CYLC_TASK_WORK_DIR}"
    cd "${CYLC_TASK_WORK_DIR}"
    # User Environment, Pre-Script, Script and Post-Script
    typeset func_name=
    for func_name in 'user_env' 'pre_script' 'script' 'post_script'; do
        cylc__job__run_inst_func "${func_name}"
    done
    # Empty work directory remove
    cd
    rmdir "${CYLC_TASK_WORK_DIR}" 2>'/dev/null' || true
    # Send task succeeded message
    wait "${CYLC_TASK_MESSAGE_STARTED_PID}" 2>'/dev/null' || true
    cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" 'succeeded' || true
    # (Ignore shellcheck "globbing and word splitting" warning here).
    # shellcheck disable=SC2086
    trap '' ${CYLC_VACATION_SIGNALS:-} ${CYLC_FAIL_SIGNALS}
    # Execute success exit script
    cylc__job__run_inst_func 'exit_script'
    exit 0
}

###############################################################################
# Run a function in the task job instance file, if possible.
# Arguments:
#   func_name: name of function without the "cylc__job__inst__" prefix
# Returns:
#   return 0, or the return code of the function if called
cylc__job__run_inst_func() {
    typeset func_name="$1"
    shift 1
    if typeset -f "cylc__job__inst__${func_name}" 1>'/dev/null' 2>&1; then
        "cylc__job__inst__${func_name}" "$@"
    fi
}

###############################################################################
# Send message (and possibly run err script) before job exit.
# Globals:
#   CYLC_FAIL_SIGNALS
#   CYLC_TASK_MESSAGE_STARTED_PID
#   CYLC_VACATION_SIGNALS
# Arguments:
#   signal: trapped or given signal
#   run_err_script (boolean): run job err script or not
#   messages (remaining arguments):
#     messages to send back to the suite server program,
#     see "cylc help message" for format of messages.
# Returns:
#   exit 1
cylc__job_finish_err() {
    typeset signal="$1"
    typeset run_err_script="$2"
    shift 2
    typeset signal_name=
    # (Ignore shellcheck "globbing and word splitting" warning here).
    # shellcheck disable=SC2086
    trap '' ${CYLC_VACATION_SIGNALS:-} ${CYLC_FAIL_SIGNALS}
    if [[ -n "${CYLC_TASK_MESSAGE_STARTED_PID:-}" ]]; then
        wait "${CYLC_TASK_MESSAGE_STARTED_PID}" 2>'/dev/null' || true
    fi
    cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" "$@" || true
    if "${run_err_script}"; then
        cylc__job__run_inst_func 'err_script' "${signal}" >&2
    fi
    exit 1
}

###############################################################################
# Wrap cylc__job_finish_err to abort with a user-defined error message.
cylc__job_abort() {
    cylc__job_finish_err "EXIT" true "CRITICAL: aborted/\"${1}\""
}

###############################################################################
# Wrap cylc__job_finish_err for job preempt/vacation signal trap.
cylc__job_vacation() {
    cylc__job_finish_err "${1}" false "WARNING: vacated/${1}"
}

###############################################################################
# Wrap cylc__job_finish_err for automatic job exit signal trap.
cylc__job_err() {
    cylc__job_finish_err "${1}" true "CRITICAL: failed/${1}"
}

###############################################################################
# Handle dummy job cycle point specific success or failure.
# Globals:
#   CYLC_TASK_TRY_NUMBER
#   CYLC_TASK_CYCLE_POINT
#   CYLC_CYCLING_MODE
# Arguments:
#   fail_try_1_only (boolean): fail only on 1st try
#   fail_cycle_points (remaining arguments):
#     'all': fail all cycle points
#     'P1 P2 P3 ...': fail these cycle points
# Returns:
#   0 - dummy job succeed
#   1 - dummy job fail
cylc__job__dummy_result() {
    typeset fail_try_1_only="$1"; shift
    typeset fail_cycle_points="$*"
    typeset fail_this_point=false
    if [[ "${fail_cycle_points}" == *all* ]]; then
        # Fail all points.
        fail_this_point=true
    else
        # Fail some or no points.
        if [[ "${CYLC_CYCLING_MODE}" == "integer" ]]; then
            for POINT in ${fail_cycle_points}; do
                if ((CYLC_TASK_CYCLE_POINT == POINT)); then
                    fail_this_point=true
                    break
                fi
            done
        else
            for POINT in ${fail_cycle_points}; do
                if cylc cyclepoint --equal="$POINT"; then
                    fail_this_point=true
                    break
                fi
            done
        fi
    fi
    if ! $fail_this_point || \
            ($fail_try_1_only && ((CYLC_TASK_TRY_NUMBER > 1)) ); then
        echo "(dummy job succeed)"
        return 0
    else
        >&2 echo "(dummy job fail)"
        return 1
    fi
}
