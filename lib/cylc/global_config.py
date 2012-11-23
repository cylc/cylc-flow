#!/usr/bin/env python

import os, sys
from configobj import ConfigObj, ConfigObjError, get_extra_values, flatten_errors, Section
from validate import Validator
from print_cfg import print_cfg
from mkdir_p import mkdir_p
import atexit
import shutil
from tempfile import mkdtemp
from mkdir_p import mkdir_p

class globalcfg( object ):

    def __init__( self ):
        # site config file
        site_cfg_spec = os.path.join( os.environ['CYLC_DIR'], 'conf', 'site', 'cfgspec' )
        site_cfg_file = os.path.join( os.environ['CYLC_DIR'], 'conf', 'site', 'site.rc' )
        # user config files (default and user overide)
        user_cfg_spec   = os.path.join( os.environ['CYLC_DIR'], 'conf', 'user', 'cfgspec' )
        dusr_cfg_file = os.path.join( os.environ['CYLC_DIR'], 'conf', 'user', 'cylc.rc' )
        ousr_cfg_file   = os.path.join( os.environ['HOME'], '.cylc', 'cylc.rc' )

        site_cfg = {}
        dusr_cfg = {}
        ousr_cfg = {}

        to_validate = {}
        if os.path.isfile( site_cfg_file ):
            try:
                site_cfg = ConfigObj( infile=site_cfg_file, configspec=site_cfg_spec )
            except ConfigObjError, x:
                print >> sys.stderr, x
                raise SystemExit( "ERROR, failed to load site config file: " + site_cfg_file )
            else:
                to_validate['site'] = site_cfg

        if os.path.isfile( dusr_cfg_file ):
            try:
                dusr_cfg = ConfigObj( infile=dusr_cfg_file, configspec=user_cfg_spec )
            except ConfigObjError, x:
                print >> sys.stderr, x
                raise SystemExit( "ERROR, failed to load default user config file: " + dusr_cfg_file )
            else:
                to_validate['default user'] = dusr_cfg

        if os.path.isfile( ousr_cfg_file ):
            try:
                ousr_cfg = ConfigObj( infile=ousr_cfg_file, configspec=user_cfg_spec )
            except ConfigObjError, x:
                print >> sys.stderr, x
                raise SystemExit( "ERROR, failed to load your user config file: " + ousr_cfg_file )
            else:
                to_validate['user'] = ousr_cfg 

        # validate and load defaults
        for key, cfg in to_validate.items():
            val = Validator()
            test = cfg.validate( val, preserve_errors=False )
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
                raise SystemExit( "ERROR gcontrol.rc validation failed")
            extras = []
            for sections, name in get_extra_values( cfg ):
                extra = ' '
                for sec in sections:
                    extra += sec + ' / '
                extras.append( extra + name )
            if len(extras) != 0:
                for extra in extras:
                    print >> sys.stderr, '  ERROR, illegal entry:', extra 
                raise SystemExit( "ERROR illegal gcontrol.rc entry(s) found" )

        # combine site and user config into a global config
        if ousr_cfg:
            self.inherit( dusr_cfg, ousr_cfg ) # user overrides defaults
        self.inherit( dusr_cfg, site_cfg )     # add in site items 
        self.cfg = dusr_cfg

        # process temporary directory
        cylc_tmpdir = self.cfg['temporary directory']
        if not cylc_tmpdir:
            # use tempfile.mkdtemp() to create a new temp directory
            cylc_tmpdir = mkdtemp(prefix="cylc-")
            # self-cleanup
            atexit.register(lambda: shutil.rmtree(cylc_tmpdir))
        else:
            cylc_tmpdir = os.path.expanduser( os.path.expandvars( cylc_tmpdir) )
            try:
                mkdir_p( cylc_tmpdir )
            except Exception,x:
                print >> sys.stderr, x
                print >> sys.stderr, 'ERROR, illegal temporary directory?', cylc_tmpdir
                sys.exit(1)
        # now replace the original item
        self.cfg['temporary directory'] = cylc_tmpdir

        # expand out environment variables and ~user in file paths
        for key,val in self.cfg['documentation'].items():
            if not key.endswith( 'file' ):
                continue
            else:
                self.cfg['documentation'][key] = os.path.expanduser( os.path.expandvars( val ))

        # expand out $HOME in ports file directory
        self.cfg['location of suite port files'] = os.path.expandvars( self.cfg['location of suite port files'] )
        try:
            mkdir_p( self.cfg['location of suite port files'] )
        except Exception, x:
            print >> sys.stderr, x
            raise SuiteConfigError, 'ERROR, illegal dir? ' + self.cfg['location of suite port files']

    def inherit( self, target, source ):
        for item in source:
            if isinstance( source[item], dict ):
                if item not in target:
                    target[item] = {}
                self.inherit( target[item], source[item] )
            else:
                if source[item]:
                    target[item] = source[item]

    def dump( self, cfg_in=None ):
        if cfg_in:
            print_cfg( cfg_in, prefix='   ' )
        else:
            print_cfg( self.cfg, prefix='   ' )

