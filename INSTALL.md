# Cylc Installation.

**See [The Cylc User Guide](https://cylc.github.io/cylc/documentation.html) for
detailed instructions.**

Note: *to run distributed suites Cylc must be installed on task hosts as well
as suite hosts.*

### External Software Packages.

Several external packages required on suite hosts are not needed on task hosts:
*graphviz*, and *pygraphviz*.  These should only need to be installed
once, and then updated infrequently.

### Installing Cylc

Download the latest release tarball from https://github.com/cylc/cylc/releases.

```bash
cd /home/admin/cylc/
tar xzf ~/Downloads/cylc-7.2.1.tar.gz
# DO NOT CHANGE THE NAME OF THE UNPACKED SOURCE DIRECTORY.
cd cylc-7.2.1
export PATH=$PWD/bin:$PATH
make  # (see below)
```

Successive Cylc versions should be installed side-by-side under a location such
as `/opt/cylc/` and invoked via a central wrapper that selects between the
available versions. This allows long-running suites (and their task jobs) to
stick with older Cylc versions if necessary. The wrapper should be edited to
point to your Cylc install location made available to users, e.g. if
`/usr/local/bin/` is in `$PATH`:

```bash
cp admin/cylc-wrapper /usr/local/bin/cylc
# (now edit 'cylc' as per in-file instructions...)
```

When you type `make`:
  * A file called VERSION is created from the name of the sourc directory.
  * The Cylc documentation is generated from source, in doc/install/.

### Installing The Documentation

After running `make` you can copy the entire `doc/install` directory to a
convenient location such as `/var/www/html/`, and update your Cylc site config 
file to point to the intranet location.

### Cloning The Cylc Repository

To participate in Cylc development fork [Cylc on
GitHub](https://github.com/cylc/cylc) and clone it locally.  Changes should be
developed in feature branches then pushed to your GitHub fork before issuing a
Pull Request to the team. Please discuss proposed changes before you begin
work.
