
Building

```bash
$ docker build -t slurm:test .
$ docker run --name slurm --hostname docker --rm -d slurm:test
```

Accessing

```bash
$ docker exec -ti slurm /bin/bash
```
