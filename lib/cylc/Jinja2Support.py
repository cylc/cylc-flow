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

import os, sys, re
import glob
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, TemplateError, StrictUndefined

"""cylc support for the Jinja2 template processor. Importing code should
catch ImportError in case Jinja2 is not installed."""

def load_template_vars( pairs, pairs_file, verbose=False ):
    res = {}
    if pairs_file:
        if os.path.isfile( pairs_file ):
            tvf = open( pairs_file, 'r' )
            lines = tvf.readlines()
            for line in lines:
                # remove trailing comments:
                line = re.sub( '#.*$', '', line )
                line = line.strip()
                if re.match( '^\s*$', line ):
                    # skip blank lines:
                    continue
                var, val = line.split('=')
                var = var.strip()
                val = val.strip()
                res[var] = val
            tvf.close()
        else:
            raise TemplateError, "ERROR: template vars file not found: " + pairs_file
    for i in pairs:
        var, val = i.split('=')
        var = var.strip()
        val = val.strip()
        res[var] = val
    if verbose:
        print 'Setting Jinja2 template variables:'
        for var, val in res.items():
            print '    + ', var, '=', val

    return res

def Jinja2Process( flines, dir, inputs=[], inputs_file=None, verbose=False ):
    env = Environment( loader=FileSystemLoader(dir), undefined=StrictUndefined, extensions=['jinja2.ext.do'] )

    # Load any custom Jinja2 filters in the suite definition directory
    # Example: a filter to pad integer values some fill character:
    #|(file SUITE_DEFINIION_DIRECTORY/Jinja2/foo.py)
    #|  #!/usr/bin/env python
    #|  def foo( value, length, fillchar ):
    #|     return str(value).rjust( int(length), str(fillchar) )
    fdirs = [os.path.join( os.environ['CYLC_DIR'], 'lib', 'Jinja2Filters' ),
            os.path.join( dir, 'Jinja2Filters' ),
            os.path.join( os.path.join( os.environ['HOME'], '.cylc', 'Jinja2Filters' ))]
    usedfdirs = []
    for fdir in fdirs:
        if os.path.isdir( fdir ):
            usedfdirs.append( fdir )
    for filterdir in usedfdirs:
        sys.path.append( os.path.abspath( filterdir ))
        for f in glob.glob( os.path.join( filterdir, '*.py' )):
            fname = os.path.basename( f ).rstrip( '.py' )
            # TODO - EXCEPTION HANDLING FOR LOADING CUSTOM FILTERS
            m = __import__( fname )
            env.filters[ fname ] = getattr( m, fname )

    # Import SUITE HOST USER ENVIRONMENT into template:
    # (usage e.g.: {{environ['HOME']}}).
    env.globals['environ'] = os.environ

    # load file lines into a template, excluding '#!jinja2' so
    # that '#!cylc-x.y.z' rises to the top.
    # CALLERS SHOULD HANDLE JINJA2 TEMPLATESYNTAXERROR AND TEMPLATEERROR
    # try:
    template = env.from_string( '\n'.join(flines[1:]) )
    # except Exception, x:
    #     # This happens if we use an unknown Jinja2 filter, for example.
    ##     # TODO - THIS IS CAUGHT BY VALIDATE BUT NOT BY VIEW COMMAND...
    #     raise TemplateError( x )
    try:
        template_vars = load_template_vars( inputs, inputs_file, verbose )
    except Exception, x:
        raise TemplateError( x )
    
    # CALLERS SHOULD HANDLE JINJA2 TEMPLATESYNTAXERROR AND TEMPLATEERROR
    # AND TYPEERROR (e.g. for not using "|int" filter on number inputs.
    # Convert unicode to plain str, ToDo - still needed for parsec?)
    #try:
    rendered = str( template.render( template_vars ) )
    #except Exception, x:
    #    raise TemplateError( x )

    xlines = rendered.split('\n')
    suiterc = []
    for line in xlines:
        # Jinja2 leaves blank lines where source lines contain
        # only Jinja2 code; this matters if line continuation
        # markers are involved, so we remove blank lines here.
        if re.match( '^\s*$', line ):
            continue
            # restoring newlines here is only necessary for display by
        # the cylc view command:
        ###suiterc.append(line + '\n')
        suiterc.append(line)

    return suiterc

