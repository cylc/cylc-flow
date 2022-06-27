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
#------------------------------------------------------------------------------
# USAGE
#   Sets up bash auto-completion for cylc commands, workflows, tasks and more.
#
#   Make a copy and source this file in your ~/.bash_profile file like this:
#
#   if [[ $- =~ i && -f /path/to/cylc-completion.bash ]]; then
#       . /path/to/cylc-completion.bash
#   fi
#
#   Cylc will launch a "completion server" to perform completions. The
#   server will shut itself down when idle. When it does you may see a line
#   like this in your console:
#     [1]+  Done                    coproc COPROC cylc completion-server
#
#   To adjust the timeout see the --timeout option of "cylc completion-server".
#
#   Administrators may want to place this file in the
#   /etc/bash_completion.d/ (or equivalent) directory.
#------------------------------------------------------------------------------

export CYLC_COMPLETION_LANG=bash
export CYLC_COMPLETION_SCRIPT_VERSION=1.0.0

_cylc_completion () {
    # start the completion server if needed
    if [[ -z ${COPROC[0]} ]]; then
        {
            coproc cylc completion-server
        } >/dev/null 2>/dev/null  # suppress cproc output (includes PID)
    fi

    # send a completion request
    echo "$(
        IFS='|' 
        echo "${COMP_WORDS[*]}"
    )" >&"${COPROC[1]}" # shellcheck disable=SC2005
    # (shellcheck disable because subshell needed to set IFS)

    # read a completion response
    read -a COMPREPLY <&"${COPROC[0]}"

    # tell Bash whether or not to follow the completion with a space
    if [[ ${COMPREPLY[0]} = */ ]]; then
        compopt -o nospace
    else
        compopt +o nospace
    fi
}

complete -F _cylc_completion cylc
