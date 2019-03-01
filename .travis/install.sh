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

set -eu
set -o xtrace
shopt -s extglob

# Travis-CI install

args=("$@")

if grep -E '(unit-tests|functional-tests)' <<< "${args[@]}"; then
    sudo apt-get install heirloom-mailx
    # coverage dependencies
    pip install coverage pytest-cov mock
    # common Cylc reqirements
    pip install colorama python-jose zmq
fi

if grep 'unit-tests' <<< "${args[@]}"; then
    pip install pycodestyle pytest mock
    # TODO: EmPy removed from testing, see:  #2958
fi

# install dependencies required for building documentation
if grep 'docs' <<< "${args[@]}$"; then
    pip install sphinx
    # for PDF output via LaTeX builder
    sudo apt-get install texlive-latex-base
fi

# configure local SSH for Cylc jobs
ssh-keygen -t rsa -f ~/.ssh/id_rsa -N "" -q
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
ssh-keyscan -t rsa localhost >> ~/.ssh/known_hosts
