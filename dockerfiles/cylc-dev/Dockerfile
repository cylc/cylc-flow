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

FROM conda/miniconda3:latest

LABEL version="1.0" \
      description="Image with Cylc installed with Conda from a working copy."

ARG CONDA_ENV="cylc8"
ARG CYLC_FLOW_DIR="./"

# suppress bizarre error messages
# mesg: ttyname failed: Inappropriate ioctl for device
RUN sed -i 's/mesg.*/tty -s \&\& &/' "$HOME/.profile"

# install cylc dependencies
RUN apt-get update && \
    # build-deps: build-essential
    # run deps: procps 
    apt-get -qq -y install build-essential procps rsync && \
    # install conda stuff
    conda init bash && \
    . ./usr/local/etc/profile.d/conda.sh && \
    conda create -y -n "$CONDA_ENV" && \
    conda install -y -n "$CONDA_ENV" --only-deps -c conda-forge cylc-flow && \
    conda clean -y --all && \
    # tidy up after ourselves
    apt-get -y remove build-essential && \
    apt-get autoclean && \
    echo "conda activate $CONDA_ENV" >> $HOME/.bashrc

# copy in cylc source files
COPY "$CYLC_FLOW_DIR" "cylc"

# run setup logic
RUN pip install -e ./cylc && \
    cylc version
