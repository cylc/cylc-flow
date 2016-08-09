# Cylc Installation.

**See [The Cylc User Guide](https://cylc.github.io/cylc/documentation.html) for
detailed instructions.**

Note: *to run distributed suites cylc must be installed on task hosts as well as suite
hosts.*

### External Software Packages.

Several external packages required on suite hosts are not needed on task hosts:
*Jinja2*, *graphviz*, and *pygraphviz*.  These should only need to be installed
once, and then updated infrequently.

### Installing Cylc Releases

Download the latest release tarball from https://github.com/cylc/cylc/releases.

Cylc releases should be installed in parallel under a top level `cylc`
directory such as `/opt/cylc/` or `/home/admin/cylc/`.

```bash
cd /home/admin/cylc/
tar xzf ~/Downloads/cylc-6.10.0.tar.gz
cd cylc-6.10.0
export PATH=$PWD/bin:$PATH
make  # (see below)
```

Cylc is accessed via a central wrapper script can select between installed
versions. This allows long-running suites to stick with older cylc versions
if necessary. The wrapper should be modified slightly to point to your
local installation (see comments in-script) and then installed (once) in
`$PATH` for users, e.g.:
```bash
cp admin/cylc-wrapper /usr/local/bin/cylc
```

When you type `make`: 
  * A file called VERSION will be created to hold the cylc version string,
  e.g. "6.10.0".  This is taken from the name of the parent directory: *do not
  change the name of the unpacked cylc source directory*.
  * The Cylc User Guide will be generated from LaTeX source files (in PDF if
  `pdflatex` is installed, and HTML if `tex4ht` and *ImageMagick* are
  installed).
  * A Python *fast ordered dictionary* module called *orrdereddict*  will be
  built from C source in `ext/ordereddict-0.4.5`.  This may give enhanced
  performance over the Python standard library, but it is optional.  To use it,
  install it manually into your `$PYTHONPATH`.

### Cloning The Cylc Repository

To get the latest bleeding-edge cylc version and participate in cylc
development, fork [cylc on GitHub](https://github.com/cylc/cylc), clone your
fork locally, develop changes locally in a new branch, then push the branch to
your fork and issue a Pull Request to the cylc development team.  Please
discuss proposed changes before you begin work, however.
