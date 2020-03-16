Building

```bash
$ docker build -t slurm:test .
$ docker run --name slurm --hostname docker -v $(realpath ../../):/root/cylc-flow --rm -d slurm:test
```

Accessing

```bash
$ docker exec -ti slurm /bin/bash
```
