<div
  align="center"
>
<img
  src="https://raw.githubusercontent.com/cylc/cylc-admin/master/docs/img/cylc-logo.svg"
  width="50%"
/>

[![PyPI](https://img.shields.io/pypi/v/cylc-flow.svg?color=yellow)](https://pypi.org/project/cylc-flow/)
[![Anaconda-Server Badge](https://anaconda.org/conda-forge/cylc-flow/badges/version.svg)](https://anaconda.org/conda-forge/cylc-flow)
[![chat](https://img.shields.io/matrix/cylc-general:matrix.org)](https://matrix.to/#/#cylc-general:matrix.org)
[![forum](https://img.shields.io/discourse/https/cylc.discourse.group/posts.svg)](https://cylc.discourse.group/)
[![Documentation](https://img.shields.io/website?label=documentation&up_message=live&url=https%3A%2F%2Fcylc.github.io%2Fcylc-doc%2Fstable%2Fhtml%2Findex.html)](https://cylc.github.io/cylc-doc/stable/html/index.html)

</div>

Cylc (pronounced silk) is a general purpose workflow engine that also
manages cycling systems very efficiently. It is used in production weather,
climate, and environmental forecasting on HPC, but is not specialized to those
domains.

### Quick Start


[Installation](https://cylc.github.io/cylc-doc/stable/html/installation.html) |
[Documentation](https://cylc.github.io/cylc-doc/stable/html/index.html)

```bash
# install cylc
conda install cylc-flow

# extract an example to run
cylc get-resources examples/2-integer-cycling

# install and run it
cylc vip integer-cycling  # vip = validate, install and play

# watch it run
cylc tui integer-cycling
```

### The Cylc Ecosystem

- [cylc-flow](https://github.com/cylc/cylc-flow) - The core Cylc Scheduler for defining and running workflows.
- [cylc-uiserver](https://github.com/cylc/cylc-uiserver) - The web-based Cylc graphical user interface for monitoring and controlling workflows.
- [cylc-rose](https://github.com/cylc/cylc-rose) - Provides integration with [Rose](http://metomi.github.io/rose/).

### Migrating From Cylc 7

[Migration Guide](https://cylc.github.io/cylc-doc/stable/html/7-to-8/index.html)
| [Migration Support](https://cylc.discourse.group/c/cylc/7-to-8/13)

Cylc 8 can run most Cylc 7 workflows in compatibility mode with little to no
changes, go through the
[migration guide](https://cylc.github.io/cylc-doc/stable/html/7-to-8/index.html)
for more details.

Quick summary of major changes:

* Python 2 -> 3.
* Internal communications converted from HTTPS to ZMQ (TCP).
* PyGTK GUIs replaced by:
  * Terminal user interface (TUI) included in cylc-flow.
  * Web user interface provided by the cylc-uiserver package.
* A new scheduling algorithm with support for branched workflows.
* Command line changes:
  * `cylc run <id>` -> `cylc play <id>`
  * `cylc restart <id>` -> `cylc play <id>`
  * `rose suite-run` -> `cylc install; cylc play <id>`
* The core package containing Cylc scheduler program has been renamed cylc-flow.
* Cylc review has been removed, the Cylc 7 version remains Cylc 8 compatible.


### Citations & Publications

[![DOI](https://zenodo.org/badge/1836229.svg)](https://zenodo.org/badge/latestdoi/1836229)
[![JOSS](http://joss.theoj.org/papers/10.21105/joss.00737/status.svg)](https://doi.org/10.21105/joss.00737)
[![CISE](https://img.shields.io/website/https/ieeexplore.ieee.org/document/8675433.svg?color=orange&label=CISE&up_message=10.1109%2FMCSE.2019.2906593)](https://ieeexplore.ieee.org/document/8675433)

### Copyright and Terms of Use

[![License](https://img.shields.io/github/license/cylc/cylc-flow.svg?color=lightgrey)](https://github.com/cylc/cylc-flow/blob/master/COPYING)

Copyright (C) 2008-<span actions:bind='current-year'>2026</span> NIWA & British Crown (Met Office) & Contributors.

Cylc is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Cylc is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Cylc.  If not, see [GNU licenses](http://www.gnu.org/licenses/).

### Contributing

[![Contributors](https://img.shields.io/github/contributors/cylc/cylc-flow.svg?color=9cf)](https://github.com/cylc/cylc-flow/graphs/contributors)
[![Commit activity](https://img.shields.io/github/commit-activity/m/cylc/cylc-flow.svg?color=yellowgreen)](https://github.com/cylc/cylc-flow/commits/master)
[![Last commit](https://img.shields.io/github/last-commit/cylc/cylc-flow.svg?color=ff69b4)](https://github.com/cylc/cylc-flow/commits/master)

Contributions welcome:

* Read the [contributing](https://github.com/cylc/cylc-flow/blob/master/CONTRIBUTING.md) page.
* Development setup instructions are in the
  [developer docs](https://cylc.github.io/cylc-admin/#cylc-8-developer-docs).
* Involved change proposals can be found in the
  [admin pages](https://cylc.github.io/cylc-admin/#change-proposals).
* Touch base in the
  [developers chat](https://matrix.to/#/#cylc-general:matrix.org).

This repository contains some code that was generated by GitHub Copilot.
