#!/usr/bin/env python

import os, sys, re
from copy import deepcopy
from cylc.owner import user
import atexit
import shutil
from tempfile import mkdtemp
from envvar import expandvars
from mkdir_p import mkdir_p
from cfgspec.site_spec import get_cfg, print_cfg

gcfg = None

class GlobalConfigError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class globalcfg( object ):
    """
    Handle global (all suites) site and user configuration for cylc.
    User file values override site file values.
   
    For all derived items - paths hardwired under the configurable top
    levels - use the get_derived_host_item(suite,host) method.
    """
    def __init__( self, strict=False, verbose=False ):
        """Parse, validate, and combine site and user files.""" 

        self.verbose = verbose
        self.strict = strict # not used yet

        try:
            self.cfg = get_cfg( self.verbose )
        except Exception, x:
            print >> sys.stderr, x
            raise GlobalConfigError("ABORTING")

        # Expand environment variables and ~user in LOCAL file paths.
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

    def get_host_item( self, item, host=None, owner=None, replace=False ):
        """This allows use of hosts with no entry in the config file to
        default to appropriately modified localhost settings."""

        value = None
        if host and host != 'localhost':
            # see if we have an explicit entry for this host item
            try:
                value = self.cfg['hosts'][host][item]
            except KeyError:
                # no we don't
                pass

        if not value:
            # default to the value for localhost.
            value = self.cfg['hosts']['localhost'][item]

        if value:
            # localhost items may default to None too (e.g. cylc bin directory)
            if (host and host != 'localhost') or (owner and owner != user ) or replace:
                # item requested for a remote account
                if 'directory' in item:
                    # Replace local home directory, if it appears, with
                    # literal '$HOME' for evaluation on the remote account.
                    value = value.replace( os.environ['HOME'], '$HOME' )
        return value

    def get_derived_host_item( self, suite, item, host=None, owner=None, replace=False ):
        """Compute hardwired paths relative to the configurable top dirs."""

        # suite run dir
        srdir = os.path.join( self.get_host_item( 'run directory',  host, owner, replace ), suite )
        # suite workspace
        swdir = os.path.join( self.get_host_item( 'work directory', host, owner, replace ), suite )

        # if invoked by the "cylc submit" command we modify the top
        # level directory names to avoid contaminating suite output.
        try:
            if os.environ['CYLC_MODE'] == 'submit':
                srdir += '-submit'
                swdir += '-submit'
        except:
            pass

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

    def roll_directory( self, d, name, archlen=0 ):
        """
        Create a directory after rolling back any previous instances of it.
        e.g. if archlen = 2 we keep: d, d.1, d.2. If 0 keep no old ones.
        """
        for n in range( archlen, -1, -1 ): # archlen...0
            if n > 0:
                dpath = d+'.'+str(n)
            else:
                dpath = d
            if os.path.exists( dpath ):
                if n >= archlen:
                    # remove oldest backup
                    shutil.rmtree( dpath )
                else:
                    # roll others over
                    os.rename( dpath, d+'.'+str(n+1) )
        self.create_directory( d, name )

    def create_directory( self, d, name ):
        try:
            mkdir_p( d )
        except Exception, x:
            print >> sys.stderr, str(x)
            raise GlobalConfigError( 'Failed to create directory "' + name + '"' )

    def create_cylc_run_tree( self, suite, verbose=False ):
        """Create all top-level cylc-run output directories on the suite host."""

        if verbose:
            print 'Creating the suite output tree:'

        item = 'suite run directory'
        if verbose:
            print ' +', item
        idir = self.get_derived_host_item( suite, item )
        if self.cfg['enable run directory housekeeping']:
            self.roll_directory( idir, item, self.cfg['run directory rolling archive length'] )

        for item in [
                'suite log directory',
                'suite job log directory',
                'suite state directory',
                'suite work directory',
                'suite share directory']:
            if verbose:
                print ' +', item
            idir = self.get_derived_host_item( suite, item )
            self.create_directory( idir, item )

        item = 'temporary directory'
        value = self.cfg[item]
        if value:
            self.create_directory( value, item )

        item = '[pyro]ports directory'
        value = self.cfg['pyro']['ports directory']
        self.create_directory( value, item )
        
def get_global_cfg( strict=False, verbose=False ):
    global gcfg
    if gcfg is None:
        gcfg = globalcfg( strict=strict, verbose=verbose )
    return gcfg

def print_global_cfg():
    print_cfg()

