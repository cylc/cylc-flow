# Cylc: Quick Installation Guide

**See [The Cylc User Guide](https://cylc.github.io/cylc/documentation.html) for
more detailed information.**

Cylc must be installed on suite and task job hosts. Third-party dependencies
(below) are not required on job hosts.

### Third-party Software Packages

Install the packages listed in the **Installation** section of the User Guide.
See also *Check Software Installation* below.

### Installing Cylc

Download the latest tarball from [Cylc
Releases](https://github.com/cylc/cylc/releases).

Successive Cylc releases should be installed side-by-side under a location
such as `/opt`:

```bash
cd /opt
tar xzf cylc-7.7.0.tar.gz
# DO NOT CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY.
cd cylc-7.7.0
export PATH=$PWD/bin:$PATH
make
```

Then make (or update) a symlink to the latest installed version:
```bash
ln -s /opt/cylc-7.7.0 /opt/cylc
```

When you type `make`:
  * A file called VERSION is created, containing the Cylc version number
    * The version number is taken from the name of the parent directory. DO
      NOT CHANGE THE NAME OF THE UNPACKED CYLC SOURCE DIRECTORY
  * The Cylc documentation is generated from source and put in doc/install/
    (if you have pdflatex, tex4ht, and several other LateX packages installed).

If this is the first installed version of Cylc, copy the wrapper script
`usr/bin/cylc` to a location in the system executable path, such as
`/usr/bin/` or `/usr/local/bin/`, and edit it - as per the in-file
instructions - to point to the Cylc install location:

```bash
cp /opt/cylc-7.7.0/usr/bin/cylc /usr/local/bin/
# (and EDIT /usr/local/bin/cylc as instructed)
```

The wrapper is designed invoke the latest (symlinked) version of Cylc by
default, or else a particular version determined by `$CYLC_VERSION` or
`$CYLC_HOME` in your environment. This is how a long-running suite server
program ensures that the jobs it manages invoke clients at the right cylc
version.

### Check Software Installation

```
$ cylc check-software
Checking your software...

Individual results:
===============================================================================
Package (version requirements)                          Outcome (version found)
===============================================================================
                              *REQUIRED SOFTWARE*                              
Python (2.6+, <3).....................FOUND & min. version MET (2.7.12.final.0)

                  *OPTIONAL SOFTWARE for the HTML User Guide*                  
ImageMagick (any)...............................................FOUND (6.8.9-9)

            *OPTIONAL SOFTWARE for the HTTPS communications layer*            
Python:urllib3 (any).............................................FOUND (1.13.1)
Python:OpenSSL (any).............................................FOUND (17.2.0)

                 *OPTIONAL SOFTWARE for the LaTeX User Guide*                 
TeX:framed (any)....................................................FOUND (n/a)
TeX (3.0+)................................FOUND & min. version MET (3.14159265)
TeX:preprint (any)..................................................FOUND (n/a)
TeX:tex4ht (any)....................................................FOUND (n/a)
TeX:tocloft (any)...................................................FOUND (n/a)
TeX:texlive (any)...................................................FOUND (n/a)
===============================================================================

Summary:
                         ****************************                         
                             Core requirements: ok                             
                            Full-functionality: ok                            
                         ****************************  
```

### Installing The Documentation

After running `make`, copy the `doc/install` directory to a location such as
`/var/www/html/` and update your Cylc site config file to point to it.
