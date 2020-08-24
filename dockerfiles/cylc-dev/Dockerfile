# NOTE: as this copies the cylc-flow code this image must be built from
# the root cylc-flow directory i.e:
# $ docker build -f dockerfiles/cylc-deps/Dockerfile -t cylc-dev:latest .

FROM conda/miniconda3:latest

ARG CONDA_ENV="cylc8"
ARG CYLC_FLOW_DIR="./"

# install cylc dependencies

RUN apt-get update && \
    # build-deps: build-essential
    # run deps: procps 
    apt-get -qq -y install build-essential procps && \
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
