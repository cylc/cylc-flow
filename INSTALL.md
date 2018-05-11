# Cylc Installation.

**See [The Cylc User Guide](https://cylc.github.io/cylc/documentation.html) for
detailed instructions.**

Cylc must be installed on suite and task job hosts, although the external
software packages (below) are not required on job hosts.

### Required External Software Packages

These can be installed once on suite hosts updated infrequently.

 * graphviz
 * pygraphviz

### Installing Cylc

Download the latest tarball from https://github.com/cylc/cylc/releases.

Successive Cylc releases should be installed side-by-side under a location such
as `/opt`:

```bash
cd /opt
tar xzf cylc-7.7.0.tar.gz
# DO NOT CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY.
cd cylc-7.7.0
export PATH=$PWD/bin:$PATH
make
```

When you type `make`:
  * A file called VERSION is created, containing the Cylc version number
    * The version number is taken from the name of the parent directory: DO NOT
      CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY
  * The Cylc documentation is generated from source and put in doc/install/

Once installed, Cylc commands should be invoked via the supplied central
wrapper script that selects between the available versions. This allows
long-running suites (and their task jobs) to stick with older versions if
necessary. The wrapper should be edited to point to the Cylc install location:

```bash
cp /opt/cylc-7.7.0/sbin/cylc-wrapper /usr/local/bin/cylc
# (now edit '/usr/local/bin/cylc' as per in-file instructions...)
```

Finally, make a symlink to the latest installed version:
```bash
ln -s /opt/cylc-7.7.0 /opt/cylc
```
(This will be the default version invoked by the wrapper if a specific version is not requested via \lstinline=$CYLC_VERSION=.

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
