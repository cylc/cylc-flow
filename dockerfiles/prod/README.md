A docker image intended as a primer for real-world usage.

This Dockerfile builds a Conda environment with cylc-flow and cylc-rose installed.

The Conda environment is auto-activated via the Bash entry point, but also via
the `.bashrc` files for any Bash processes started via other services (e.g,
SSH).

### Build:

```console
$ docker build . -f Dockerfile -t cylc-prod:latest
```

### Run:

```console
$ docker run -it cylc-flow:latest
# cylc version --long
Cylc 8.x.x   ....

Plugins:
  cylc-rose    1.x.x  ....
```
