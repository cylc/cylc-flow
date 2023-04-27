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
      description="Cylc remote job host for background & at jobs."

# install deps
RUN  \
    apt-get -qq -y install ssh iputils-ping && \
    apt-get autoclean

# copy public ssh key (don't setup two way ssh)
COPY .docker-ssh-keys/*.pub .ssh/

# authorise that key
RUN \
    mkdir ~/.ssh -p && \
    chmod 700 ~/.ssh && \
    touch ~/.ssh/authorized_keys && \
    chmod 600 ~/.ssh/authorized_keys && \
    cat .ssh/cylc-docker.pub >> ~/.ssh/authorized_keys

# expose port 22 for ssh
EXPOSE 22

# copy a script for configuring /etc/hosts
COPY dockerfiles/cylc-remote/configure bin/host-configure

# configure on boot and start the required services
ENTRYPOINT \
    service ssh start && \
    atd && \
    /bin/host-configure && \
    /usr/bin/env bash
