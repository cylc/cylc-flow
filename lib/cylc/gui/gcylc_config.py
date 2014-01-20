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
from cylc.task_state import task_state
from cylc.cfgspec.gcylc_spec import cfg

class config( object ):
    """gcylc user configuration - default view panels, task themes etc."""

    def __init__( self, prntcfg=False ):

        self.default_theme = "default"
        cfg.printcfg()

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
                    print >> sys.stderr, "WARNING, ingoring illegal task state '" + state + "' in theme", theme
                # reverse inherit (override)
                tcfg = deepcopy(defs)
                self.inherit( tcfg, self.parse_state(theme, item, val))
                cfg_themes[theme][state] = tcfg
        
        # final themes result:
        cfg['themes'] = cfg_themes

        # check intial view config
        views = copy(cfg['initial views'])
        for view in views:
            if view not in ['dot', 'text', 'graph' ]:
                print >> sys.stderr, "WARNING: ignoring illegal view name'" + view + '"'
                cfg['initial views'].remove( view )
        views = cfg['initial views']
        if len( views ) == 0:
            # at least one view required
            print >> sys.stderr, "WARNING: no initial views defined, defaulting to 'text'"
            cfg['initial views'] = ['text']

        # store final result
        self.cfg = cfg

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

