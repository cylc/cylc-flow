# Cylc Installation.

**See [The Cylc User Guide](https://cylc.github.io/cylc/documentation.html) for
detailed instructions.**

Cylc must be installed on suite and task job hosts. Third-party dependencies
(below) are not required on job hosts.

### Required Third-party Software Packages

These can be installed on suite hosts, and updated very infrequently.

 * graphviz
 * pygraphviz

### Installing Cylc

Download the latest tarball from [Cylc
Releases](https://github.com/cylc/cylc/releases).

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
    * The version number is taken from the name of the parent directory. DO NOT
      CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY
  * The Cylc documentation is generated from source and put in doc/install/ (if
    you have pdflatex, tex4ht, and several other LateX packages installed).

Cylc commands should be invoked via a central wrapper script that you need to
copy from sbin/cylc-wrapper to (say) /usr/local/bin/ and rename it as "cylc".
The wrapper selects between available versions, allowing long-running suites
(and their task jobs) to stick with older versions if necessary. The wrapper
should be edited to point to the Cylc install location:

```bash
cp /opt/cylc-7.7.0/sbin/cylc-wrapper /usr/local/bin/cylc
# (Now EDIT /usr/local/bin/cylc as per the in-file instructions...)
```

Finally, make a symlink to the latest installed version:
```bash
ln -s /opt/cylc-7.7.0 /opt/cylc
```
(The wrapper will invoke this version if \lstinline=$CYLC_VERSION= is not set).

### Installing The Documentation

After running `make`, copy the `doc/install` directory to a location such as
`/var/www/html/` and update your Cylc site config file to point to it.

### Cloning The Cylc Repository

To participate in Cylc development fork [Cylc on
GitHub](https://github.com/cylc/cylc) and clone it locally. Changes should be
developed in feature branches then pushed to your GitHub fork before issuing a
Pull Request to the team. Please post an Issue to discuss proposed changes
before you begin any signficant work.
