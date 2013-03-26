#!/usr/bin/env python

import os, sys, re
from configobj import ConfigObj, ConfigObjError, get_extra_values, flatten_errors, Section
from validate import Validator
from print_cfg import print_cfg
from copy import deepcopy
import atexit
import shutil
from tempfile import mkdtemp
from envvar import expandvars

# TODO: drop now-broken support for Python 2.4
try:
    any
except NameError:
    # any() appeared in Python 2.5
    def any(iterable):
        for entry in iterable:
            if entry:
                return True
        return False


class GlobalConfigError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)


class globalcfg( object ):
    """Handle global (all suites) site and user configuration for cylc.
    Legal items and default values are defined in a single configspec
    file.  Special comments in the configspec file denote items that can
    only be overridden by a site config file; otherwise a user config
    file can override site values (which override the defaults).

    Local host settings can be used directly; for other hosts use the
    get_host_item(host) method; it knows how to use modified local
    settings as defaults.
    
    For all derived items - paths hardwired under the configurable top
    levels - use the get_derived_host_item(suite,host) method."""

    def __init__( self ):
        """Load defaults, site, and user config files (in reverse order
        of precedence) to generate the global config structure; validate
        to catch errors; disallow user config of site-only items.""" 

        try:
            self.load()
        except Exception, x:
            raise
            print >> sys.stderr, x
            print >> sys.stderr, "Failed to load load cylc site/user config:"
            print >> sys.stderr, "  + " + self.rcfiles['site']
            print >> sys.stderr, "  + " + self.rcfiles['user']
            raise GlobalConfigError("ABORTING")

    def load( self ):
        # location of the configspec file
        cfgspec = os.path.join( os.environ['CYLC_DIR'], 'conf', 'siterc', 'cfgspec' )

        # location of the site and user config files
        self.rcfiles = {
                'site' : os.path.join( os.environ['CYLC_DIR'], 'conf', 'siterc', 'site.rc' ),
                'user' : os.path.join( os.environ['HOME'], '.cylc', 'user.rc' )}

        # load the (sparse) user file
        rc = self.rcfiles['user']

        self.usercfg = ConfigObj( infile=rc, configspec=cfgspec )

        # load the (sparse) site file
        rc = self.rcfiles['site']

        self.sitecfg = ConfigObj( infile=rc, configspec=cfgspec, _inspec=False )

        # generate a configobj with all defaults loaded from the configspec
        # (and call it self.cfg as we re-use it below for the final result)
        self.cfg = ConfigObj( configspec=cfgspec )
        self.validate( self.cfg ) # (validation loads the default settings)

        # check the user file for any attempt to override site-onlyitems
        self.block_user_cfg( self.usercfg, self.cfg, self.cfg.comments )

        # merge site config into defaults (site takes precedence)
        self.cfg.merge( self.sitecfg )
        # now merge user config for final result (user takes precedence) 
        self.cfg.merge( self.usercfg )

        # now validate the final result to catch any errors
        self.validate( self.cfg )

        self.expand_local_paths()

    def expand_local_paths( self ):
        """Expand environment variables and ~user in LOCAL file paths."""

        for key,val in self.cfg['documentation']['files'].items():
            self.cfg['documentation']['files'][key] = expandvars( val )

        self.cfg['pyro']['ports directory'] = expandvars( self.cfg['pyro']['ports directory'] )

        for key,val in self.cfg['hosts']['localhost'].items():
            if val and key and key.endswith('directory'):
                self.cfg['hosts']['localhost'][key] = expandvars( val )


    def get_tmpdir( self ):
        """Make a new temporary directory and arrange for it to be
        deleted automatically when we're finished with it. Call this
        explicitly just before use to ensure the directory is not
        deleted by other processes before it is needed. THIS IS
        CURRENTLY ONLY USED BY A FEW CYLC COMMANDS. If cylc suites
        ever need it this must be called AFTER FORKING TO DAEMON MODE or
        atexit() will delete the directory when the initial process
        exits after forking."""

        tdir = self.cfg['temporary directory']
        if tdir:
            tdir = expandvars( tdir )
            tmpdir = mkdtemp(prefix="cylc-", dir=expandvars(tdir) )
        else:
            tmpdir = mkdtemp(prefix="cylc-")
        # self-cleanup
        atexit.register(lambda: shutil.rmtree(tmpdir))
        # now replace the original item to allow direct access
        self.cfg['temporary directory'] = tmpdir
        return tmpdir

    def write_rc( self, ftype=None ):
        """Generate initial site or user config files containing all
        available settings commented out.  In the user case the default
        values are obtained by any site settings into the configspec 
        defaults."""
        if ftype not in [ 'site', 'user' ]:
            raise GlobalConfigError( "ERROR, illegal file type for write_rc(): " + ftype )

        target = self.rcfiles[ ftype ] 

        if os.path.exists( target ):
            raise GlobalConfigError( "ERROR, file already exists: " + target )

        # cfgobj.write() will write a config file directly, but we want
        # add a file header, filter out some lines, and comment out all
        # the default settings ... so read into a string and process.

        if target == 'site':
            preamble = """
#_______________________________________________________________________
#       This is your cylc site configuration file, generated by:
#               'cylc get-global-config --write-site'
#-----------------------------------------------------------------------
#    Users can override these settings in $HOME/.cylc/user.rc, see:
#               'cylc get-global-config --write-user'
#-----------------------------------------------------------------------
# At the time of writing this file contained all available config items,
# commented out with '#==>', with initial values determined by the cylc
# system defaults in $CYLC_DIR/conf/site/cfgspec.
#-----------------------------------------------------------------------
# ** TO CUSTOMIZE, UNCOMMENT AND MODIFY SPECIFIC SETTINGS AS REQUIRED **
#          (just the items whose values you need to change)
#-----------------------------------------------------------------------
"""
        else:
            preamble = """
#_______________________________________________________________________
#       This is your cylc user configuration file, generated by:
#               'cylc get-global-config --write-user'
#-----------------------------------------------------------------------
# At the time of writing this file contained all available config items,
# commented out with '#==>', with initial values determined by the local
# site config file $CYLC_DIR/conf/site/siter.rc, or by the cylc system
# defaults in $CYLC_DIR/conf/site/cfgspec.
#-----------------------------------------------------------------------
# ** TO CUSTOMIZE, UNCOMMENT AND MODIFY SPECIFIC SETTINGS AS REQUIRED **
#          (just the items whose values you need to change)
#-----------------------------------------------------------------------
"""
        # start with a copy of the site config
        cfg = deepcopy( self.sitecfg )
        # validate to load defaults for items not set in site config
        self.validate( cfg )

        # write out all settings, commented out.
        outlines = preamble.split('\n')
        cfg.filename = None
        for iline in cfg.write():
            line = iline.strip()
            if line.startswith( "#>" ):
                # omit comments specific to the spec file
                continue
            if line != '':
                line = re.sub( '^(\s*)([^[#]+)$', '\g<1>#==> \g<2>', line )
            outlines.append(line)

        f = open( target, 'w' )
        for line in outlines:
            print >> f, line
        f.close()

        print "File written:", target
        print "See in-file comments for customization information."

    def validate( self, cfg ):
        # validate against the cfgspec and load defaults
        val = Validator()
        test = cfg.validate( val, preserve_errors=False, copy=True )
        if test != True:
            # Validation failed
            failed_items = flatten_errors( cfg, test )
            # Always print reason for validation failure
            for item in failed_items:
                sections, key, result = item
                print >> sys.stderr, ' ',
                for sec in sections:
                    print >> sys.stderr, sec, ' / ',
                print >> sys.stderr, key
                if result == False:
                    print >> sys.stderr, "ERROR, required item missing."
                else:
                    print >> sys.stderr, result
            raise GlobalConfigError( "ERROR global config validation failed")
        extras = []
        for sections, name in get_extra_values( cfg ):
            extra = ' '
            for sec in sections:
                extra += sec + ' / '
            extras.append( extra + name )
        if len(extras) != 0:
            for extra in extras:
                print >> sys.stderr, '  Illegal item:', extra 
            raise GlobalConfigError( 'ERROR: illegal site/user config items detected' )

    def block_user_cfg( self, usercfg, sitecfg, comments={}, sec_blocked=False ):
        """Check the comments for each item for the user exclusion indicator."""
        for item in usercfg:
            if item not in comments:
                # => an illegal item, it will be caught by validation
                continue

            # iterate through sparse user config and check for attempts
            # to override any items marked '# SITE ONLY' in the spec.
            if item not in comments:
                # some items need not be in site config (e.g.
                # user-specified task hosts).
                break
            if isinstance( usercfg[item], dict ):
                if any( re.match( '^\s*# SITE ONLY\s*$', mem ) for mem in comments[item]):
                    # section blocked, but see if user actually attempts
                    # to set any items in it before aborting.
                    sb = True
                else:
                    sb = False
                self.block_user_cfg( usercfg[item], sitecfg[item], sitecfg[item].comments, sb )
            else:
                if any( re.match( '^\s*# SITE ONLY\s*$', mem ) for mem in comments[item]):
                    raise GlobalConfigError( 'ERROR, item blocked from user override: ' + item )
                elif sec_blocked:
                    raise GlobalConfigError( 'ERROR, section blocked from user override, item: ' + item )

    def dump( self, cfg_in=None ):
        if cfg_in:
            print_cfg( cfg_in, prefix='   ' )
        else:
            print_cfg( self.cfg, prefix='   ' )

    def get_host_item( self, item, host=None, owner=None ):
        """This allows use of hosts with no entry in the config file to
        default to appropriately modified localhost settings."""

        value = None
        if host and host is not 'localhost':
            # see if we have an explicit entry for this host item
            try:
                value = self.cfg['hosts'][host][item]
            except KeyError:
                # no we don't
                pass

        if not value:
            # default to the value for localhost.
            value = self.cfg['hosts']['localhost'][item]
            # TODO: consolidate with is_remote tests elsewhere:
            if (host and host is not 'localhost') or (owner and owner is not user ):
                # time requested for a remote account
                if 'directory' in item:
                    # Replace local home directory, if it appears, with
                    # literal '$HOME' for evaluation on the remote account.
                    value = value.replace( os.environ['HOME'], '$HOME' )
        return value

    def get_derived_host_item( self, suite, item, host=None, owner=None ):
        """Compute hardwired paths relative to the configurable top dirs."""

        # suite run dir
        srdir = os.path.join( self.get_host_item( 'run directory',  host, owner ), suite )
        # suite workspace
        swdir = os.path.join( self.get_host_item( 'work directory', host, owner ), suite )

        if item == 'suite run directory':
            value = srdir

        elif item == 'suite log directory':
            value = os.path.join( srdir, 'log', 'suite' )

        elif item == 'suite job log directory':
            value = os.path.join( srdir, 'log', 'job' )

        elif item == 'suite state directory':
            value = os.path.join( srdir, 'state' )

        elif item == 'suite work directory':
            value = os.path.join( swdir, 'work' )
 
        elif item == 'suite share directory':
            value = os.path.join( swdir, 'share' )

        else:
            raise GlobalConfigError( "Illegal derived item: " + item )

        return value

# instantiate a global config object for use in other modules
gcfg = globalcfg()

