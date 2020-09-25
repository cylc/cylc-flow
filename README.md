# The Cylc Workflow Engine

**Project**: [![PyPI](https://img.shields.io/pypi/v/cylc-flow.svg?color=yellow)](https://pypi.org/project/cylc-flow/) [![Anaconda-Server Badge](https://anaconda.org/conda-forge/cylc-flow/badges/version.svg)](https://anaconda.org/conda-forge/cylc-flow) [![Anaconda-Server Badge](https://anaconda.org/conda-forge/cylc-flow/badges/downloads.svg)](https://anaconda.org/conda-forge/cylc-flow) [![License](https://img.shields.io/github/license/cylc/cylc-flow.svg?color=lightgrey)](https://github.com/cylc/cylc-flow/blob/master/COPYING) [![Website](https://img.shields.io/website/https/cylc.github.io.svg?color=green&up_message=live)](https://cylc.github.io/) [![Documentation](https://img.shields.io/website/https/cylc.github.io/doc/built-sphinx/index.html.svg?color=red&label=documentation&up_message=live)](https://cylc.github.io/doc/built-sphinx/index.html)

**Support**: [![Discourse](https://img.shields.io/discourse/https/cylc.discourse.group/posts.svg?color=blueviolet)](https://cylc.discourse.group/)

**References**: [![DOI](https://zenodo.org/badge/1836229.svg)](https://zenodo.org/badge/latestdoi/1836229) [![JOSS](http://joss.theoj.org/papers/10.21105/joss.00737/status.svg)](https://doi.org/10.21105/joss.00737) [![CISE](https://img.shields.io/website/https/ieeexplore.ieee.org/document/8675433.svg?color=orange&label=CISE&up_message=10.1109%2FMCSE.2019.2906593)](https://ieeexplore.ieee.org/document/8675433)

**Development**: [![Contributors](https://img.shields.io/github/contributors/cylc/cylc-flow.svg?color=9cf)](https://github.com/cylc/cylc-flow/graphs/contributors) [![Commit activity](https://img.shields.io/github/commit-activity/m/cylc/cylc-flow.svg?color=yellowgreen)](https://github.com/cylc/cylc-flow/commits/master) [![Last commit](https://img.shields.io/github/last-commit/cylc/cylc-flow.svg?color=ff69b4)](https://github.com/cylc/cylc-flow/commits/master)

Cylc ("silk") orchestrates complex distributed suites of interdependent cycling
(or non-cycling) tasks. It was originally designed to automate environmental
forecasting systems at [NIWA](https://www.niwa.co.nz), however Cylc is a
general workflow engine; it is not specialized to forecasting in any way.

### Python 2 or Python 3 ?

Currently in the source code repository:
 - **master branch:** Python 3, ZeroMQ network layer, *no GUI* -  **Cylc-8 Work In Progress**
 - **7.8.x branch:** Python 2, Cherrypy network layer, PyGTK GUI - **Cylc-7 Maintenance**

The first official Cylc-8 release (with a new web UI) is not expected until late 2019.
Until then we recommend the latest cylc-7.8 release for production use.

[Quick Installation](INSTALL.md) |
[Website](https://cylc.github.io/) |
[Documentation](https://cylc.github.io/documentation) |
[Contributing](CONTRIBUTING.md)

### Copyright and Terms of Use

Copyright (C) 2008-2020 NIWA & British Crown (Met Office) & Contributors.
 
Cylc is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.
 
Cylc is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.
 
You should have received a copy of the GNU General Public License along with
Cylc.  If not, see [GNU licenses](http://www.gnu.org/licenses/).

## Cylc Documentation
 * See [The Cylc Website](https://cylc.github.io/)
