FROM ubuntu:latest

ENV DEBIAN_FRONTEND noninteractive

# Based on:
#  - https://bitbucket.org/deardooley/agave-docker/src/master/test-containers/schedulers/slurm/Dockerfile
#  - https://ubuntuforums.org/showthread.php?t=2404746
#  - https://stackoverflow.com/questions/46966876/installing-emulating-slurm-on-an-ubuntu-16-04-desktop-slurmd-fails-to-start

RUN apt-get update && apt-get install -y \
    lsof \
    munge \
    slurm-wlm \
    supervisor \
    python3.7 \
    python3-pip \
    python3.7-dev \
    && python3.7 -m pip install -U pip setuptools \
    && rm -rf /var/lib/apt/lists/*

RUN set -x \
    && mkdir /var/run/slurm-llnl/ \
        /var/run/slurmd \
        /var/run/slurmdbd \
        /var/lib/slurmd \
        /var/log/slurm \
        /var/run/munge \
    && touch /var/lib/slurmd/node_state \
        /var/lib/slurmd/front_end_state \
        /var/lib/slurmd/job_state \
        /var/lib/slurmd/resv_state \
        /var/lib/slurmd/trigger_state \
        /var/lib/slurmd/assoc_mgr_state \
        /var/lib/slurmd/assoc_usage \
        /var/lib/slurmd/qos_usage \
        /var/lib/slurmd/fed_mgr_state \
    && /usr/sbin/create-munge-key -f \
    && chown -R slurm:slurm /var/*/slurm* \
    && chown -R root:root /var/log/munge \
    && chown -R root:root /var/run/slurm-llnl \
	&& chown -R root:root /var/lib/munge \
	&& chown -R root:root /var/run/munge \
	&& chown -R root:root /etc/munge

COPY slurm.conf /etc/slurm-llnl/slurm.conf
COPY supervisord.conf /etc/supervisord.conf

COPY slurm.submit /root/slurm.submit

VOLUME ["/root/cylc-flow"]

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV USER=root

WORKDIR /

COPY flow-tests.rc /root/.cylc/flow/8.0a1/flow-tests.rc

EXPOSE 10389 6817 6818
CMD /usr/bin/supervisord
