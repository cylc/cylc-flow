#!/bin/bash
# ^ NOTE: this script is not invoked directly so the shell is decided by
#         the calling script, this just helps shellcheck lint the file

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

###############################################################################
# Bash functions for a cylc job.
###############################################################################

###############################################################################
# The main function for a cylc job.
cylc__job__main() {
    # Export CYLC_ workflow and task environment variables
    cylc__job__inst__cylc_env
    # Turn on xtrace in debug mode
    if "${CYLC_DEBUG:-false}"; then
        if [[ -n "${BASH:-}" ]]; then
            PS4='+[\D{%Y%m%dT%H%M%S%z}]\u@\h '
            exec 19>>"${CYLC_RUN_DIR}/${CYLC_WORKFLOW_ID}/log/job/${CYLC_TASK_JOB}/job.xtrace"
            export BASH_XTRACEFD=19
            >&2 echo "Sending DEBUG MODE xtrace to job.xtrace"
        fi
        set -x
    fi
    # Init-Script
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
    # Write job self-identify
    USER="${USER:-$(whoami)}"
    typeset host="${HOSTNAME:-}"
    if [[ -z "${host}" ]]; then
        if [[ "$(uname)" == 'AIX' ]]; then
            # On AIX the hostname command has no '-f' option
            host="$(hostname).$(namerslv -sn 2>'/dev/null' | awk '{print $2}')"
        else
            host="$(hostname -f)"
        fi
    fi
    # Developer Note:
    # We were using a HERE document for writing info here until we notice that
    # Bash uses temporary files for HERE documents, which can be inefficient.
    echo "Workflow : ${CYLC_WORKFLOW_ID}"
    echo "Job : ${CYLC_TASK_JOB} (try ${CYLC_TASK_TRY_NUMBER})"
    echo "User@Host: ${USER}@${host}"
    echo
    # Derived environment variables
    export CYLC_WORKFLOW_RUN_DIR="${CYLC_RUN_DIR}/${CYLC_WORKFLOW_ID}"
    export CYLC_WORKFLOW_LOG_DIR="${CYLC_WORKFLOW_RUN_DIR}/log/scheduler"
    export CYLC_WORKFLOW_SHARE_DIR="${CYLC_WORKFLOW_RUN_DIR}/share"
    export CYLC_WORKFLOW_WORK_DIR="${CYLC_WORKFLOW_RUN_DIR}/work"
    export CYLC_TASK_CYCLE_POINT="${CYLC_TASK_JOB%%/*}"
    export CYLC_TASK_NAME="${CYLC_TASK_JOB#*/}"
    CYLC_TASK_NAME="${CYLC_TASK_NAME%/*}"
    if [[ "${CYLC_CYCLING_MODE}" != "integer" ]]; then  # i.e. date-time cycling
        export ISODATETIMECALENDAR="${CYLC_CYCLING_MODE}"
        export ISODATETIMEREF="${CYLC_TASK_CYCLE_POINT}"
    fi
    # The "10#" part ensures that the submit number is interpreted in base 10.
    # Otherwise, a zero padded number will be interpreted as an octal.
    export CYLC_TASK_SUBMIT_NUMBER="$((10#${CYLC_TASK_JOB##*/}))"
    export CYLC_TASK_ID="${CYLC_TASK_CYCLE_POINT}/${CYLC_TASK_NAME}"
    export CYLC_TASK_LOG_DIR="${CYLC_WORKFLOW_RUN_DIR}/log/job/${CYLC_TASK_JOB}"
    export CYLC_TASK_LOG_ROOT="${CYLC_TASK_LOG_DIR}/job"
    if [[ -n "${CYLC_TASK_WORK_DIR_BASE:-}" ]]; then
        # Note: value of CYLC_TASK_WORK_DIR_BASE may contain variable
        # substitution syntax including some of the derived variables above, so
        # it can only be derived at point of use.
        CYLC_TASK_WORK_DIR_BASE="$(eval echo "${CYLC_TASK_WORK_DIR_BASE}")"
    else
        CYLC_TASK_WORK_DIR_BASE="${CYLC_TASK_CYCLE_POINT}/${CYLC_TASK_NAME}"
    fi
    export CYLC_TASK_WORK_DIR="${CYLC_WORKFLOW_WORK_DIR}/${CYLC_TASK_WORK_DIR_BASE}"
    export CYLC_TASK_SHARE_CYCLE_DIR="${CYLC_WORKFLOW_SHARE_DIR}/cycle/${CYLC_TASK_CYCLE_POINT}"
    typeset contact="${CYLC_WORKFLOW_RUN_DIR}/.service/contact"
    if [[ -f "${contact}" ]]; then
        # (contact file not present for polled platforms)
        CYLC_WORKFLOW_HOST="$(sed -n 's/^CYLC_WORKFLOW_HOST=//p' "${contact}")"
        CYLC_WORKFLOW_OWNER="$(sed -n 's/^CYLC_WORKFLOW_OWNER=//p' "${contact}")"
        export CYLC_WORKFLOW_HOST CYLC_WORKFLOW_OWNER
        # BACK COMPAT: DEPRECATED environment variables
        # remove at:
        #     Cylc8.x
        export CYLC_SUITE_HOST="${CYLC_WORKFLOW_HOST}"
        export CYLC_SUITE_OWNER="${CYLC_WORKFLOW_OWNER}"
    fi

    # BACK COMPAT: DEPRECATED environment variables
    # remove at:
    #     Cylc8.x
    export CYLC_SUITE_SHARE_DIR="${CYLC_WORKFLOW_SHARE_DIR}"
    export CYLC_SUITE_SHARE_PATH="${CYLC_WORKFLOW_SHARE_DIR}"
    export CYLC_SUITE_NAME="${CYLC_WORKFLOW_ID}"
    export CYLC_SUITE_LOG_DIR="${CYLC_WORKFLOW_LOG_DIR}"
    export CYLC_SUITE_INITIAL_CYCLE_POINT="${CYLC_WORKFLOW_INITIAL_CYCLE_POINT}"
    export CYLC_SUITE_INITIAL_CYCLE_TIME="${CYLC_WORKFLOW_INITIAL_CYCLE_POINT}"
    export CYLC_SUITE_FINAL_CYCLE_POINT="${CYLC_WORKFLOW_FINAL_CYCLE_POINT}"
    export CYLC_SUITE_FINAL_CYCLE_TIME="${CYLC_WORKFLOW_FINAL_CYCLE_POINT}"
    export CYLC_SUITE_WORK_DIR="${CYLC_WORKFLOW_WORK_DIR}"
    export CYLC_SUITE_UUID="${CYLC_WORKFLOW_UUID}"
    export CYLC_SUITE_RUN_DIR="${CYLC_WORKFLOW_RUN_DIR}"
    export CYLC_SUITE_DEF_PATH="${CYLC_WORKFLOW_RUN_DIR}"
    export CYLC_TASK_CYCLE_TIME="${CYLC_TASK_CYCLE_POINT}"
    export CYLC_TASK_WORK_PATH="${CYLC_TASK_WORK_DIR}"

    # Send task started message
    cylc message -- "${CYLC_WORKFLOW_ID}" "${CYLC_TASK_JOB}" 'started' &
    CYLC_TASK_MESSAGE_STARTED_PID=$!
    # System paths:
    # * workflow directory (installed run-dir first).
    export PATH="${CYLC_WORKFLOW_RUN_DIR}/share/bin:${CYLC_WORKFLOW_RUN_DIR}/bin:${PATH}"
    export PYTHONPATH="${CYLC_WORKFLOW_RUN_DIR}/share/lib/python:${CYLC_WORKFLOW_RUN_DIR}/lib/python:${PYTHONPATH:-}"
    # Create share and work directories
    mkdir -p "${CYLC_TASK_SHARE_CYCLE_DIR}" || true
    mkdir -p "$(dirname "${CYLC_TASK_WORK_DIR}")" || true
    mkdir -p "${CYLC_TASK_WORK_DIR}"
    cd "${CYLC_TASK_WORK_DIR}"
    # Env-Script, User Environment, Pre-Script, Script and Post-Script
    # Run user scripts in subshell to protect cylc job script from interference.
    # Waiting on background process allows signal traps to trigger immediately.
    cylc__job__run_user_scripts &
    CYLC_TASK_USER_SCRIPT_PID=$!
    wait "${CYLC_TASK_USER_SCRIPT_PID}" || {
        # Check return code for signals (value greater than 128).
        typeset ret_code="$?"
        if ((ret_code > 128)); then
            # Trigger the EXIT trap if the process exited due to a signal.
            exit "$ret_code"
        else
            # Trigger ERR trap while preserving the exit code
            # (NB: Bash versions are buggy and neither return statement nor
            # subshelled exit won't do here.)
            cylc__set_return "$ret_code"
        fi
    }
    # Empty work directory remove
    cd
    rmdir "${CYLC_TASK_WORK_DIR}" 2>'/dev/null' || true
    # Send task succeeded message
    wait "${CYLC_TASK_MESSAGE_STARTED_PID}" 2>'/dev/null' || true
    cylc message -- "${CYLC_WORKFLOW_ID}" "${CYLC_TASK_JOB}" 'succeeded' || true
    # (Ignore shellcheck "globbing and word splitting" warning here).
    # shellcheck disable=SC2086
    trap '' ${CYLC_VACATION_SIGNALS:-} ${CYLC_FAIL_SIGNALS}
    # Execute success exit script
    cylc__job__run_inst_func 'exit_script'
    exit 0
}

###############################################################################
# Run user scripts.
cylc__job__run_user_scripts() {
    typeset func_name=
    for func_name in 'env_script' 'user_env' 'pre_script' \
           'script' 'post_script'; do
        cylc__job__run_inst_func "${func_name}"
    done
}

###############################################################################
# Set last return code (needed to work around Bash bugs in ERR trapping).
cylc__set_return() {
    return "${1:-0}"
}

###############################################################################
# Disable selected or all (if no arguments given) fail traps.
# Globals:
#   CYLC_FAIL_SIGNALS
cylc__job__disable_fail_signals() {
    if [[ "$#" == '0' ]]; then
        CYLC_FAIL_SIGNALS=
    else
        typeset signal=
        for signal in "$@"; do
            CYLC_FAIL_SIGNALS="${CYLC_FAIL_SIGNALS/${signal}/}"
        done
    fi
}

###############################################################################
# Wait for background `cylc message started` command to finish.
# Globals:
#   CYLC_TASK_MESSAGE_STARTED_PID
# Returns:
#   0 (always success)
cylc__job__wait_cylc_message_started() {
    if [[ -n "${CYLC_TASK_MESSAGE_STARTED_PID:-}" ]]; then
        while kill -s 0 -- "${CYLC_TASK_MESSAGE_STARTED_PID}" 2>'/dev/null'; do
            sleep 1
        done
    fi
}

###############################################################################
# Poll existence of pattern from workflow log for up to a minute.
cylc__job__poll_grep_workflow_log() {
    local TIMEOUT="$(($(date +%s) + 60))" # wait 1 minute
    while ! grep -s "$@" "${CYLC_WORKFLOW_LOG_DIR}/log"; do
        sleep 1
        if (($(date +%s) > TIMEOUT)); then
            echo "ERROR: poll timed out: grep -s $* ${CYLC_WORKFLOW_LOG_DIR}/log" >&2
            exit 1
        fi
    done
}

###############################################################################
# Run a function in the job instance file, if possible.
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
#   CYLC_TASK_LOG_ROOT
#   CYLC_TASK_MESSAGE_STARTED_PID
#   CYLC_TASK_USER_SCRIPT_PID
#   CYLC_TASK_USER_SCRIPT_EXITCODE
#   CYLC_VACATION_SIGNALS
# Arguments:
#   signal: trapped or given signal
#   run_err_script (boolean): run job err script or not
#   messages (remaining arguments):
#     messages to send back to the scheduler,
#     see "cylc help message" for format of messages.
# Returns:
#   exit ${CYLC_TASK_USER_SCRIPT_EXITCODE}
cylc__job_finish_err() {
    CYLC_TASK_USER_SCRIPT_EXITCODE="${CYLC_TASK_USER_SCRIPT_EXITCODE:-$?}"
    typeset signal="$1"
    typeset run_err_script="$2"
    shift 2
    # (Ignore shellcheck "globbing and word splitting" warning here).
    # shellcheck disable=SC2086
    trap '' ${CYLC_VACATION_SIGNALS:-} ${CYLC_FAIL_SIGNALS}
    if [[ -n "${CYLC_TASK_MESSAGE_STARTED_PID:-}" ]]; then
        wait "${CYLC_TASK_MESSAGE_STARTED_PID}" 2>'/dev/null' || true
    fi
    # Propagate real signals to entire process group, if we are a group leader,
    # otherwise just to the backgrounded user script.
    if [[ -n "${CYLC_TASK_USER_SCRIPT_PID:-}" ]] &&
       [[ "${signal}" != "ERR" ]] && [[ "${signal}" != "EXIT" ]]; then
        kill -s "${signal}" -- "-$$" 2>'/dev/null' ||
        kill -s "${signal}" -- "${CYLC_TASK_USER_SCRIPT_PID}" 2>'/dev/null' || true
    fi
    grep -q "^CYLC_JOB_EXIT=" "${CYLC_TASK_LOG_ROOT}.status" ||
    cylc message -- "${CYLC_WORKFLOW_ID}" "${CYLC_TASK_JOB}" "$@" &
    CYLC_TASK_MESSAGE_FINISHED_PID=$!
    if "${run_err_script}"; then
        cylc__job__run_inst_func 'err_script' "${signal}" >&2
    fi
    wait "${CYLC_TASK_MESSAGE_FINISHED_PID}"
    exit "${CYLC_TASK_USER_SCRIPT_EXITCODE}"
}

###############################################################################
# Wrap cylc__job_finish_err to abort with a user-defined error message.
# Globals:
#   CYLC_TASK_USER_SCRIPT_EXITCODE
cylc__job_abort() {
    CYLC_TASK_USER_SCRIPT_EXITCODE="1"
    cylc__job_finish_err "EXIT" false "CRITICAL: aborted/\"${1}\""
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
