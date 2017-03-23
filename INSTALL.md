# Cylc Installation.

**See [The Cylc User Guide](https://cylc.github.io/cylc/documentation.html) for
detailed instructions.**

Cylc must be installed on task job hosts as well as suite hosts.

### Required External Software Packages

These are only needed on suite hosts (not job hosts). They can be installed
once and updated infrequently.

 * graphviz
 * pygraphviz

### Installing Cylc

Download the latest tarball from https://github.com/cylc/cylc/releases.

```bash
cd /home/admin/cylc/
tar xzf ~/Downloads/cylc-7.2.1.tar.gz
# DO NOT CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY.
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
  * A file called VERSION is created, containing the Cylc version number
    * The version number is taken from the name of the parent directory: DO NOT
      CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY
  * The Cylc documentation is generated from source and put in doc/install/

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
