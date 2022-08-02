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

Cylc (pronounced silk) is a general purpose workflow engine
that specialises in cycling workflows and has strong scaling characteristics.

Cylc was originally developed to meet the challenges of production weather
forecasting - which is notorious for the size and complexity of its workflows.

### Quick Start


[Installation](https://cylc.github.io/cylc-doc/stable/html/installation.html) |
[Documentation](https://cylc.github.io/cylc-doc/stable/html/index.html)

```bash
# install cylc
conda install cylc-flow

# write your first workflow
mkdir -p ~/cylc-src/example
cat > ~/cylc-src/example/flow.cylc <<__CONFIG__
[scheduling]
    initial cycle point = 1
    cycling mode = integer
    [[graph]]
        P1 = """
            a => b => c & d
            b[-P1] => b
        """
[runtime]
    [[a, b, c, d]]
        script = echo "Hello $CYLC_TASK_NAME"
__CONFIG__

# install and run it
cylc install example
cylc play example

# watch it run
cylc tui example
```

### Citations & Publications

[![DOI](https://zenodo.org/badge/1836229.svg)](https://zenodo.org/badge/latestdoi/1836229)
[![JOSS](http://joss.theoj.org/papers/10.21105/joss.00737/status.svg)](https://doi.org/10.21105/joss.00737)
[![CISE](https://img.shields.io/website/https/ieeexplore.ieee.org/document/8675433.svg?color=orange&label=CISE&up_message=10.1109%2FMCSE.2019.2906593)](https://ieeexplore.ieee.org/document/8675433)

### Copyright and Terms of Use

[![License](https://img.shields.io/github/license/cylc/cylc-flow.svg?color=lightgrey)](https://github.com/cylc/cylc-flow/blob/master/COPYING)

Copyright (C) 2008-<span actions:bind='current-year'>2022</span> NIWA & British Crown (Met Office) & Contributors.

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

* Read the [contributing](CONTRIBUTING.md) page.
* Development setup instructions are in the
  [developer docs](https://cylc.github.io/cylc-admin/#cylc-8-developer-docs).
* Involved change proposals can be found in the
  [admin pages](https://cylc.github.io/cylc-admin/#change-proposals).
* Touch base in the
  [developers chat](https://matrix.to/#/#cylc-general:matrix.org).
