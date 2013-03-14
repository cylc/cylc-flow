#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, sys, gtk
from copy import deepcopy, copy
from configobj import ConfigObj, ConfigObjError, get_extra_values, flatten_errors, Section
from validate import Validator
from cylc.task_state import task_state

class config( object ):
    """gcylc user configuration"""

    def __init__( self ):
        spec = os.path.join( os.environ['CYLC_DIR'], 'conf', 'gcylcrc', 'cfgspec' )
        dcfg_file = os.path.join( os.environ['CYLC_DIR'], 'conf', 'gcylcrc', 'themes.rc' )
        ucfg_file = os.path.join( os.environ['HOME'], '.cylc', 'gcylc.rc' )

        dcfg = {}
        ucfg = {}

        if os.path.isfile( ucfg_file ):
            # load user config
            try:
                ucfg = ConfigObj( infile=ucfg_file, configspec=spec )
            except ConfigObjError, x:
                print >> sys.stderr, x
                print >> sys.stderr, 'WARNING, failed to load gcylc user config: ' + ucfg_file

        if os.path.isfile( dcfg_file ):
            # load default config
            try:
                dcfg = ConfigObj( infile=dcfg_file, configspec=spec )
            except ConfigObjError, x:
                print >> sys.stderr, x
                print >> sys.stderr, 'WARNING, failed to load gcylc default config: ' + dcfg_file

        if not ucfg and not dcfg:
            raise SystemExit( 'ERROR: gcylc config file found' )

        # validate and load defaults from the cfgspec file
        cfgs = []
        for cfg in [ ucfg, dcfg ]:
            if cfg:
                cfgs.append(cfg)
        for cfg in cfgs:
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
                raise SystemExit( "ERROR gcylc.rc validation failed")
            extras = []
            for sections, name in get_extra_values( cfg ):
                extra = ' '
                for sec in sections:
                    extra += sec + ' / '
                extras.append( extra + name )
            if len(extras) != 0:
                for extra in extras:
                    print >> sys.stderr, '  ERROR, illegal entry:', extra 
                raise SystemExit( "ERROR illegal gcylc.rc entry(s) found" )

               
        # combine user config into default config
        self.inherit( dcfg, ucfg )

        self.default_theme = "default"

        # select the start-up theme
        self.use_theme = dcfg['use theme']

        # and check it is valid
        if self.use_theme not in dcfg['themes']:
            print >> sys.stderr, "WARNING: theme " + self.use_theme + " not found, using '" + self.default_theme + "'"
            dcfg['use theme'] = 'default'
            self.use_theme = self.default_theme

        # theme inheritance
        inherited = []
        for label in dcfg['themes']:
            hierarchy = []
            name = label
            while True:
                hierarchy.append(name) 
                if name == "default":
                    break
                if dcfg['themes'][name]['inherit']:
                    parent = dcfg['themes'][name]['inherit']
                    if parent not in dcfg['themes']:
                        print >> sys.stderr, "WARNING: undefined parent '" + parent + "' (theme '"+ label + "')"
                        parent = "default"
                else:
                    break
                name = parent
            hierarchy.reverse()
            prev = hierarchy[0]
            theme = deepcopy(dcfg['themes'][prev])
            for item in hierarchy[1:]:
                if item in inherited:
                    prev = item
                    continue
                #print 'Inherit:', item, '<--', prev
                self.inherit( theme, dcfg['themes'][item] )
                inherited.append( item )
            dcfg['themes'][label] = theme

        # expand theme data
        cfg_themes = {}
        for theme in dcfg['themes']:
            for key,val in dcfg['themes'][self.default_theme].items():
                # if this theme is missing an item take it from the default theme.
                # (not needed now)
                #if key not in dcfg['themes'][theme]:
                #    print >> sys.stderr, "WARNING: missing item '"+ key+ "' in theme '"+theme+"'; using value from default theme '"+ self.default_theme + "'"
                #    dcfg['themes'][theme][key] = val
                if not dcfg['themes'][theme][key]:
                    # (no need to warn now)
                    #print >> sys.stderr, "WARNING: empty item '"+ key+ "' in theme '"+theme+"'; using value from default theme '"+ self.default_theme + "'"
                    dcfg['themes'][theme][key] = val

            cfg_themes[theme] = {}
            defs = self.parse_state( theme, 'defaults', dcfg['themes'][theme]['defaults'] )

            for item, val in dcfg['themes'][theme].items():
                if item in [ 'inherit', 'defaults' ]:
                    continue
                state = item
                if state not in task_state.legal:
                    print >> sys.stderr, "WARNING, ingoring illegal task state '" + state + "' in theme", theme
                # reverse inherit (override)
                tcfg = deepcopy(defs)
                self.inherit( tcfg, self.parse_state(theme, item, val))
                cfg_themes[theme][state] = tcfg
        
        # final themes result:
        dcfg['themes'] = cfg_themes

        
        # check intial view config
        views = copy(dcfg['initial views'])
        for view in views:
            if view not in ['dot', 'text', 'graph' ]:
                print >> sys.stderr, "WARNING: ignoring illegal view name'" + view + '"'
                dcfg['initial views'].remove( view )
        views = dcfg['initial views']
        if len( views ) == 0:
            # at least one view required
            print >> sys.stderr, "WARNING: no initial views defined, defaulting to 'text'"
            dcfg['initial views'] = ['text']

        # store final result
        self.cfg = dcfg

    def parse_state( self, theme, name, cfglist=[] ):
        allowed_keys = ['style', 'color', 'fontcolor']
        allowed_styles = ['filled', 'unfilled']
        cfg = {}
        for item in cfglist:
            key, val = item.split('=')
            if key not in allowed_keys:
                raise SystemExit( 'ERROR, gcylc.rc, illegal: ' + theme + ': '+ name + ' = ' + cfglist )
            if key == 'color' or key == 'fontcolor':
                try:
                    gtk.gdk.color_parse( val )
                except ValueError, x:
                    print >> sys.stderr, 'ERROR', x
                    sys.exit( 'ERROR, gcylc.rc, illegal color: ' + theme + ': ' + name + '="' + item + '"')
            cfg[key] = val
        return cfg

    def inherit( self, target, source ):
        # recursive theme inheritance
        for item in source:
            if isinstance( source[item], dict ):
                if item not in target:
                    target[item] = {}
                self.inherit( target[item], source[item] )
            else:
                target[item] = source[item]

