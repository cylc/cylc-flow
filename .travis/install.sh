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

# pygtk via apt-get, necessary for both unit and functional tests
sudo apt-get install graphviz libgraphviz-dev python-gtk2-dev heirloom-mailx
# coverage dependencies
pip install coverage pytest-cov mock

# install dependencies required for running unit tests
if grep 'unit-tests' <<< "${args[@]}"; then
    pip install EmPy pyopenssl pycodestyle pytest mock
fi

# install dependencies required for running functional tests
if grep 'functional-tests' <<< "${args[@]}"; then
    # pygraphviz needs special treatment to avoid an error from "from . import release"
    pip install EmPy pyopenssl
    pip install pygraphviz \
      --install-option="--include-path=/usr/include/graphviz" \
      --install-option="--library-path=/usr/lib/graphviz/"
fi

# install dependencies required for building documentation
if grep 'docs' <<< "${args[@]}$"; then
    pip install sphinx
    sudo apt-get install texlive-latex-base
    pip install pygraphviz \
      --install-option="--include-path=/usr/include/graphviz" \
      --install-option="--library-path=/usr/lib/graphviz/"
fi

# configure local SSH for Cylc jobs
ssh-keygen -t rsa -f ~/.ssh/id_rsa -N "" -q
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
ssh-keyscan -t rsa localhost >> ~/.ssh/known_hosts
