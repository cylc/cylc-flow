# 1) The Mamba image
#    This image has mamba installed, we use it to create and pack
#    the required Conda environment.
FROM mambaorg/micromamba AS mamba

# create the environment
COPY conda-environment.yml .
RUN micromamba env create -f conda-environment.yml --prefix ./env

# pack the environment
RUN \
    micromamba create -c conda-forge -n conda-pack conda-pack && \
    micromamba run -n conda-pack conda-pack --prefix ./env -o ./packed-env.tar && \
    pwd && \
    mkdir ./venv && \
    cd ./venv && \
    tar -xf ../packed-env.tar && \
    rm ../packed-env.tar


# 2) The Cylc image
#    This has the Cylc Mamba environment installed and activated by default in
#    Bash shells. However, it does not have Mamba installed.
FROM ubuntu:latest as cylc-dev

COPY --from=mamba /tmp/venv /venv
COPY ./ /cylc

SHELL ["/bin/bash", "-c", "-l"]
ENTRYPOINT /bin/bash

# wipe the default crud then auto-activate the Cylc Mamba environment
RUN \
    rm $HOME/.bashrc && \
    echo '. /venv/bin/activate' >> $HOME/.bashrc && \
    echo "export TMPDIR=/tmp" >> $HOME/.bashrc

# unpack the Mamba environment, then install Cylc into it from source
RUN \
    /venv/bin/conda-unpack && \
    pip install --no-deps -e /cylc coverage && \
    pip cache purge && \
    cylc version --long

# install system dependencies
RUN \
    apt-get update && \
    apt-get -qq -y install procps rsync tree at && \
    apt-get autoclean
