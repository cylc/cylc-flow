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
# Test cat-view with a Jinja2 variable defined in a single cylc include-file
# TODO - another test for nested file inclusion
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
# Just inline
TEST_NAME=${TEST_NAME_BASE}-inline
cylc view -i "${WORKFLOW_NAME}" > tmp.stdout
cmp_ok tmp.stdout << EOF
#!jinja2
[meta]
    title = "Jinja2 simple ensemble example"
    description = "Auto-generation of dependencies for related tasks."

[scheduler]
    allow implicit tasks = True

# Note that depending on the structure of the workflow you may be able to
# SIMPLY use a task family name in the graph to represent the entire
# ensemble (which would be defined by inheritance under [runtime]).

{% set N_MEMBERS = 4 %}

# line \\
continuation

[scheduling]
    [[graph]]
        R1 = """ {# generate ensemble dependencies #}
        {% for I in range( 0, N_MEMBERS ) %}
          foo => mem_{{ I }} => post_{{ I }} => bar
        {% endfor %}"""
EOF
#-------------------------------------------------------------------------------
# "cylc view -j/--jinja2" should imply "-i/inline" too:
TEST_NAME=${TEST_NAME_BASE}-jinja2
cylc view -j "${WORKFLOW_NAME}" > tmp.stdout
cmp_ok tmp.stdout << EOF
[meta]
    title = "Jinja2 simple ensemble example"
    description = "Auto-generation of dependencies for related tasks."
[scheduler]
    allow implicit tasks = True
# Note that depending on the structure of the workflow you may be able to
# SIMPLY use a task family name in the graph to represent the entire
# ensemble (which would be defined by inheritance under [runtime]).
# line \\
continuation
[scheduling]
    [[graph]]
        R1 = """
          foo => mem_0 => post_0 => bar
          foo => mem_1 => post_1 => bar
          foo => mem_2 => post_2 => bar
          foo => mem_3 => post_3 => bar
        """
EOF
#-------------------------------------------------------------------------------
# line continuation joining
TEST_NAME=${TEST_NAME_BASE}-continuation
cylc view -c "${WORKFLOW_NAME}" > tmp.stdout
cmp_ok tmp.stdout << EOF
#!jinja2
[meta]
    title = "Jinja2 simple ensemble example"
    description = "Auto-generation of dependencies for related tasks."

[scheduler]
    allow implicit tasks = True

# Note that depending on the structure of the workflow you may be able to
# SIMPLY use a task family name in the graph to represent the entire
# ensemble (which would be defined by inheritance under [runtime]).

%include inc/default.jinja2

# line continuation

[scheduling]
    [[graph]]
        R1 = """ {# generate ensemble dependencies #}
        {% for I in range( 0, N_MEMBERS ) %}
          foo => mem_{{ I }} => post_{{ I }} => bar
        {% endfor %}"""
EOF
#-------------------------------------------------------------------------------
# all processing
TEST_NAME=${TEST_NAME_BASE}-process
cylc view -p "${WORKFLOW_NAME}" > tmp.stdout
cmp_ok tmp.stdout << EOF
[meta]
    title = "Jinja2 simple ensemble example"
    description = "Auto-generation of dependencies for related tasks."
[scheduler]
    allow implicit tasks = True
# Note that depending on the structure of the workflow you may be able to
# SIMPLY use a task family name in the graph to represent the entire
# ensemble (which would be defined by inheritance under [runtime]).
# line continuation
[scheduling]
    [[graph]]
        R1 = """
          foo => mem_0 => post_0 => bar
          foo => mem_1 => post_1 => bar
          foo => mem_2 => post_2 => bar
          foo => mem_3 => post_3 => bar
        """
EOF
#-------------------------------------------------------------------------------
purge
exit
