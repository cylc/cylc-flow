# The Cylc Workflow Engine

[![Build Status](https://travis-ci.org/cylc/cylc.svg?branch=master)](https://travis-ci.org/cylc/cylc)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/1d6a97bf05114066ae30b63dcb0cdcf9)](https://www.codacy.com/app/Cylc/cylc?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=cylc/cylc&amp;utm_campaign=Badge_Grade)
[![codecov](https://codecov.io/gh/cylc/cylc/branch/master/graph/badge.svg)](https://codecov.io/gh/cylc/cylc)
[![DOI](https://zenodo.org/badge/1836229.svg)](https://zenodo.org/badge/latestdoi/1836229)
[![DOI](http://joss.theoj.org/papers/10.21105/joss.00737/status.svg)](https://doi.org/10.21105/joss.00737)

Cylc (“silk”) orchestrates complex distributed suites of interdependent cycling
(or non-cycling) tasks. It was originally designed to automate environmental
forecasting systems at [NIWA](https://www.niwa.co.nz). Cylc is a general
workflow engine, however; it is not specialized to forecasting in any way.

### Python 2 or Python 3 ?

Currently in the source code repository:
 - **master branch:** Python 3, ZeroMQ network layer, **no GUI** -  **Cylc-8 Work In Progress**
 - **7.8.x branch:** Python 2, Cherrypy network layer, PyGTK GUI - **Cylc-7 Maintenance**

The first official Cylc-8 release (with a new web UI) is not expected until late 2019.
Until then we recommend the latest cylc-7.8 release for production use.

[Quick Installation](INSTALL.md) |
[Web Site](https://cylc.github.io/) |
[Documentation](https://cylc.github.io/documentation) |
[Contributing](CONTRIBUTING.md)

### Copyright and Terms of Use

Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
 
Cylc is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.
 
Cylc is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.
 
You should have received a copy of the GNU General Public License along with
Cylc.  If not, see [GNU licenses](http://www.gnu.org/licenses/).

## Cylc Documentation
 * See [The Cylc Web Site](https://cylc.github.io/)

## Acknowledgement for non-Cylc Work

See [Acknowledgement for Non-Cylc Work](ACKNOWLEDGEMENT.md).
