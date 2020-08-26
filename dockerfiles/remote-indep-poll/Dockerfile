# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
      description="Cylc remote job host."

# setup ssh
RUN apt-get -qq -y update && \
    apt-get -qq -y install ssh

# copy public ssh key (don't setup two way ssh)
COPY .docker-ssh-keys/*.pub .ssh/

# authorise that key
RUN mkdir ~/.ssh -p && \
    chmod 700 ~/.ssh && \
    touch ~/.ssh/authorized_keys && \
    chmod 600 ~/.ssh/authorized_keys && \
    cat .ssh/cylc-docker.pub >> ~/.ssh/authorized_keys

# expose port 22 for ssh
EXPOSE 22

# ensure the ssh service gets started with the container
ENTRYPOINT service ssh start && /usr/bin/env bash
