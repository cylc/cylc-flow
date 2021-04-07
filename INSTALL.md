# Cylc: Quick Installation Guide

**See [The Cylc User Guide](https://cylc.github.io/documentation.html) for
more detailed information.**  Cylc documentation is now maintained in the
cylc/cylc-doc repository on GitHub.

Cylc must be installed on scheduler and task job hosts. Third-party
dependencies (below) are not required on job hosts.

### Python 2 or Python 3 ?

Currently in the source code repository:
- **master branch:** Python 3, ZeroMQ network layer, **no GUI** - Cylc-8 Work In Progress
- **7.8.x branch:** Python 2, Cherrypy network layer, PyGTK GUI - Cylc-7 Maintenance

The first official Cylc-8 release (with a new web UI) is not expected until late 2019.
Until then we recommend the latest cylc-7.8 release for production use.

See [INSTALL.md in the 7.8.x repository branch](https://github.com/cylc/cylc-flow/blob/7.8.x/INSTALL.md), or in your unpacked 7.8.x
release, for how to install Cylc 7. You can download the latest cylc-7 release
tarball from [Cylc Releases](https://github.com/cylc/cylc-flow/releases).
