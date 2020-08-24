# docker build -f dockerfiles/remote/Dockerfile -t cylc-remote:latest .

# ssh-keygen -t rsa -b 4096 -C 'docker@localhost' -f id_rsa.docker -P ''
# cp id_rsa.docker.pub ~/cylc/

# ssh -p 42222 172.17.0.2
# ssh -p 42222 root@localhost -oIdentityFile=~/.ssh/id_rsa.docker

FROM cylc-dev

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

# expose port 22 for ssh
EXPOSE 22

# ensure the ssh service gets started with the container
ENTRYPOINT service ssh start && /usr/bin/env bash
