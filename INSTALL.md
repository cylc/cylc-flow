# Cylc Installation.

**See also [The Cylc User Guide](https://cylc.github.io/cylc/documentation.html).**

Cylc must be installed on suite and task job hosts. Third-party dependencies
(below) are not required on job hosts.

### Third-party Software Packages

Install the packages listed in the **Installation** section of the User Guide.
See also *Check Software Installation* below.

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

Now copy the wrapper script `sbin/cylc-wrapper` to (say) `/usr/local/bin/`,
rename it as just `cylc`, and edit it - as per instructions in the file - to
point to the Cylc install location:

```bash
cp /opt/cylc-7.7.0/sbin/cylc-wrapper /usr/local/bin/cylc
# (Now EDIT /usr/local/bin/cylc as per the in-file instructions...)
```

Finally, make a symlink to the latest installed version:
```bash
ln -s /opt/cylc-7.7.0 /opt/cylc
```
The central wrapper will invoke `cylc-$CYLC_VERSION` if `$CYLC_VERSION` is set
and that version is installed, or else the symlinked version as default. (Or
developers can set `$CYLC_HOME` to point to their local Cylc clone). Suite
server programs set `$CYLC_VERSION` to ensure that client programs invoked by
running task jobs (for messaging etc.) run from the same version as the
server.

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

       *OPTIONAL SOFTWARE for the GUI & dependency graph visualisation*       
Python:pygtk (2.0+)...........................FOUND & min. version MET (2.24.0)
graphviz (any)...................................................FOUND (2.38.0)
Python:pygraphviz (any)...........................................FOUND (1.3.1)

                  *OPTIONAL SOFTWARE for the HTML User Guide*                  
ImageMagick (any)...............................................FOUND (6.8.9-9)

            *OPTIONAL SOFTWARE for the HTTPS communications layer*            
Python:urllib3 (any).............................................FOUND (1.13.1)
Python:OpenSSL (any).............................................FOUND (17.2.0)
Python:requests (2.4.2+).......................FOUND & min. version MET (2.9.1)

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

### Cloning The Cylc Repository

To participate in Cylc development fork [Cylc on
GitHub](https://github.com/cylc/cylc) and make a local clone of your own fork
to work in. Changes should be developed in feature branches then pushed to
your GitHub fork before issuing a Pull Request to the team. Please post an
Issue to discuss proposed changes before you begin any signficant work.
