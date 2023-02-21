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

FROM cylc-dev

LABEL version="1.0" \
      description="Cylc with with UIS / hub installed."

# TODO: this installs from master, we we are on a maintainance branch we will
# need to pick an appropriate UIS branch
RUN . $HOME/.bashrc && \
    apt-get -qq -y install git && \
    pip install "cylc-uiserver[hub] @ git+https://github.com/cylc/cylc-uiserver"

ENTRYPOINT . $HOME/.bashrc && \
    cylc hub --port=8042
