FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive

# Based on:
#  - https://github.com/themattrix/bashup

RUN apt-get update && apt-get install -y \
    at \
    lsof \
    python3.7 \
    python3-pip \
    python3.7-dev \
    sqlite3 \
    wget \
    && python3.7 -m pip install -U pip setuptools \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /docker-scripts
COPY build-bash /docker-scripts/
COPY build-bash-versions /docker-scripts/
RUN chmod +x /docker-scripts/* \
    && mv /docker-scripts/* /usr/local/bin/ \
    && rm -rf /docker-scripts

VOLUME ["/root/cylc-flow"]

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV USER=root

WORKDIR /

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.7 1

ENV BASH_VERSIONS_DIR /bash
RUN mkdir $BASH_VERSIONS_DIR \
    && build-bash-versions 3.2 4.2 5.0

# the last parameter is the priority, the highest value is picked by default
RUN update-alternatives --install /bin/bash bash /bash/bash-3.2 1 && \
    update-alternatives --install /bin/bash bash /bash/bash-4.2 2 && \
    update-alternatives --install /bin/bash bash /bash/bash-5.0 3 && \
    update-alternatives --force --all && \
    update-alternatives --list bash

# To change the system bash version, use for example:
# `update-alternatives --set bash /bash/bash-4.2`
# Or if using a terminal, `update-alternatives --config bash` then choose one
