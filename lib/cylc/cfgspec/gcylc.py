#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

from parsec.config import config, ItemNotFoundError, itemstr
from parsec.validate import validator as vdr
from parsec.upgrade import upgrader
from parsec.util import printcfg

from cylc.task_state import task_state

"gcylc config file format."

SITE_FILE = os.path.join( os.environ['CYLC_DIR'], 'conf', 'gcylcrc', 'themes.rc' )
USER_FILE = os.path.join( os.environ['HOME'], '.cylc', 'gcylc.rc' )

SPEC = {
    'initial views' : vdr( vtype='string_list', default=["text"] ),
    'ungrouped views' : vdr( vtype='string_list', default=[] ),
    'use theme'     : vdr( vtype='string', default="default" ),
    'themes' : {
        '__MANY__' : {
            'inherit'       : vdr( vtype='string', default="default" ),
            'defaults'      : vdr( vtype='string_list' ),
            'waiting'       : vdr( vtype='string_list' ),
            'runahead'      : vdr( vtype='string_list' ),
            'held'          : vdr( vtype='string_list' ),
            'queued'        : vdr( vtype='string_list' ),
            'ready'         : vdr( vtype='string_list' ),
            'submitted'     : vdr( vtype='string_list' ),
            'submit-failed' : vdr( vtype='string_list' ),
            'running'       : vdr( vtype='string_list' ),
            'succeeded'     : vdr( vtype='string_list' ),
            'failed'        : vdr( vtype='string_list' ),
            'retrying'      : vdr( vtype='string_list' ),
            'submit-retrying' : vdr( vtype='string_list' ),
            },
        },
    }

def upg( cfg, descr ):
    u = upgrader(cfg, descr )
    u.deprecate( '5.4.3', ['themes','__MANY__', 'submitting'], ['themes','__MANY__', 'ready'] )
    u.upgrade()

class gconfig( config ):
    """gcylc user configuration - default view panels, task themes etc."""

    def transform( self ):
        """
        1) theme inheritance
        2) turn state attribute lists into dicts for easier access:
          running : color=#ff00ff, style=filled, fontcolor=black
          becomes:
             running : { color:#ff00ff, style:filled, fontcolor:black }
        """
        # Note this is only done for the dense config structure.

        self.expand()
        self.default_theme = "default"

        cfg = self.get()

        # select the start-up theme
        self.use_theme = cfg['use theme']

        # and check it is valid
        if self.use_theme not in cfg['themes']:
            print >> sys.stderr, "WARNING: theme " + self.use_theme + " not found, using '" + self.default_theme + "'"
            cfg['use theme'] = 'default'
            self.use_theme = self.default_theme

        # theme inheritance
        inherited = []
        for label in cfg['themes']:
            hierarchy = []
            name = label
            while True:
                hierarchy.append(name)
                if name == "default":
                    break
                if cfg['themes'][name]['inherit']:
                    parent = cfg['themes'][name]['inherit']
                    if parent not in cfg['themes']:
                        print >> sys.stderr, "WARNING: undefined parent '" + parent + "' (theme '"+ label + "')"
                        parent = "default"
                else:
                    break
                name = parent
            hierarchy.reverse()
            prev = hierarchy[0]
            theme = deepcopy(cfg['themes'][prev])
            for item in hierarchy[1:]:
                if item in inherited:
                    prev = item
                    continue
                #print 'Inherit:', item, '<--', prev
                self.inherit( theme, cfg['themes'][item] )
                inherited.append( item )
            cfg['themes'][label] = theme

        # expand theme data
        cfg_themes = {}
        for theme in cfg['themes']:
            for key,val in cfg['themes'][self.default_theme].items():
                if not cfg['themes'][theme][key]:
                    cfg['themes'][theme][key] = val

            cfg_themes[theme] = {}
            defs = self.parse_state( theme, 'defaults', cfg['themes'][theme]['defaults'] )

            for item, val in cfg['themes'][theme].items():
                if item in [ 'inherit', 'defaults' ]:
                    continue
                state = item
                if state not in task_state.legal:
                    print >> sys.stderr, "WARNING, ignoring illegal task state '" + state + "' in theme", theme
                # reverse inherit (override)
                tcfg = deepcopy(defs)
                self.inherit( tcfg, self.parse_state(theme, item, val))
                cfg_themes[theme][state] = tcfg

        # final themes result:
        cfg['themes'] = cfg_themes

    def check( self ):
        # check initial view config
        cfg = self.get( sparse=True )
        if 'initial views' not in cfg:
            return
        views = copy(cfg['initial views'])
        for view in views:
            if view not in ['dot', 'text', 'graph' ]:
                print >> sys.stderr, "WARNING: ignoring illegal view name '" + view + "'"
                cfg['initial views'].remove( view )
        views = cfg['initial views']
        if len( views ) == 0:
            # at least one view required
            print >> sys.stderr, "WARNING: no initial views defined, defaulting to 'text'"
            cfg['initial views'] = ['text']

    def parse_state( self, theme, name, cfglist=[] ):
        allowed_keys = ['style', 'color', 'fontcolor']
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
        for item in source:
            if isinstance( source[item], dict ):
                if item not in target:
                    target[item] = {}
                self.inherit( target[item], source[item] )
            else:
                target[item] = source[item]

    def dump( self, keys=[], sparse=False, pnative=False, prefix='', none_str='' ):
        # override parse.config.dump() to restore the list-nature of
        # theme state items
        cfg = deepcopy( self.get( [], sparse ))
        try:
            for theme in cfg['themes'].values():
                for state in theme.keys():
                    clist = []
                    for attr, val in theme[state].items():
                        clist.append( attr + '=' + val )
                    theme[state] = clist
        except:
            pass

        parents = []
        for key in keys:
            try:
                cfg = cfg[key]
            except KeyError, x:
                raise ItemNotFoundError( itemstr(parents,key) )
            else:
                parents.append(key)

        if pnative:
            print cfg
        else:
            printcfg( cfg, prefix=prefix, level=len(keys) )

# load on import if not already loaded
gcfg = None
if not gcfg:
    gcfg = gconfig( SPEC, upg )
    gcfg.loadcfg( SITE_FILE, "site config" )
    gcfg.loadcfg( USER_FILE, "user config" )
    # check and correct initial view config etc.
    gcfg.check()
    # add spec defaults and do theme inheritance
    gcfg.transform()

