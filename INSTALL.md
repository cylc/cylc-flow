# Cylc: Quick Installation Guide

### Python 2 or Python 3 ?

Currently in the source code repository:
- **master branch:** Python 3, ZeroMQ network layer, **no GUI** - Cylc-8 Work In Progress
- **7.8.x branch:** Python 2, Cherrypy network layer, PyGTK GUI - Cylc-7 Maintenance

The first official Cylc-8 release (with a new web UI) is not expected until late 2019.
Until then we recommend the latest cylc-7.8 release for production use.

**See [The Cylc User Guide](https://cylc.github.io/cylc/documentation.html) for
more detailed information.**

Cylc must be installed on suite and task job hosts. Third-party dependencies
(below) are not required on job hosts.

### Third-party Software Packages

Install the packages listed in the **Installation** section of the User Guide.
See also *Check Software Installation* below.

### Installing Cylc

Download the latest tarball from [Cylc
Releases](https://github.com/cylc/cylc/releases).

Successive Cylc releases should be installed side-by-side under a location
such as `/opt`:

```bash
cd /opt
tar xzf cylc-7.8.1.tar.gz
# DO NOT CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY.
cd cylc-7.8.1
export PATH=$PWD/bin:$PATH
make
```

Then make (or update) a symlink to the latest installed version:
```bash
ln -s /opt/cylc-7.8.1 /opt/cylc
```

When you type `make`:
  * A file called VERSION is created, containing the Cylc version number
    * The version number is taken from the name of the parent directory. DO
      NOT CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY
  * The Cylc User Guide is generated from source (if you have sphinx-doc installed).

If this is the first installed version of Cylc, copy the wrapper script
`usr/bin/cylc` to a location in the system executable path, such as
`/usr/bin/` or `/usr/local/bin/`, and edit it - as per the in-file
instructions - to point to the Cylc install location:

```bash
cp /opt/cylc-7.8.1/usr/bin/cylc /usr/local/bin/
# (and EDIT /usr/local/bin/cylc as instructed)
```

The wrapper is designed invoke the latest (symlinked) version of Cylc by
default, or else a particular version determined by `$CYLC_VERSION` or
`$CYLC_HOME` in your environment. This is how a long-running suite server
program ensures that the jobs it manages invoke clients at the right cylc
version.

### Check Software Installation

```
$ cylc check-software
Checking your software...
...
