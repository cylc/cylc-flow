#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

import sys, re

try:
    from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, TemplateError
except ImportError:
    jinja2_loaded = False
else:
    jinja2_loaded = True

def Jinja2Process( flines, dir, verbose ):
    # Callers should handle Jinja2 TemplateSyntaxError or TemplateError

    # check first line of file for template engine directive
    # (check for new empty suite.rc files - zero lines - first)
    if flines and re.match( '^#![jJ]inja2\s*', flines[0] ):
        # This suite.rc file requires processing with jinja2.
        if not jinja2_loaded:
            print >> sys.stderr, 'ERROR: This suite requires processing with the Jinja2 template engine'
            print >> sys.stderr, 'ERROR: but the Jinja2 modules are not installed in your PYTHONPATH.'
            raise TemplateError( 'Aborting (Jinja2 required).')
        if verbose:
            print "Processing the suite with Jinja2"
        env = Environment( loader=FileSystemLoader(dir) )
        # load file lines into a template, excluding '#!jinja2' so
        # that '#!cylc-x.y.z' rises to the top.
        template = env.from_string( ''.join(flines[1:]) )

        # (converting unicode to plain string; configobj doesn't like?)
        rendered = str( template.render() )

        xlines = rendered.split('\n') # pass a list of lines to configobj
        suiterc = []
        for line in xlines:
            # Jinja2 leaves blank lines where source lines contain
            # only Jinja2 code; this matters if line continuation
            # markers are involved, so we remove blank lines here.
            if re.match( '^\s*$', line ):
                continue

            # restoring newlines here is only necessary for display by
            # the cylc view command:
            suiterc.append(line + '\n')
    else:
        # This is a plain suite.rc file.
        suiterc = flines

    return suiterc

