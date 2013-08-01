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

from OrderedDict import OrderedDict
from parsec.validate import validator as vdr
from parsec.validate import validate, expand, get_defaults
from parsec.upgrade import upgrader, converter
from parsec.printcfg import print_nested
from parsec.fileparse import parse

"""
Define all legal items and values for cylc suite definition files.
""" 

cfg = None

SPEC = {
    'title'                                   : vdr( vtype='string', default="No title provided" ),
    'description'                             : vdr( vtype='string', default="No description provided" ),
    'cylc' : {
        'UTC mode'                            : vdr( vtype='boolean', default=False),
        'required run mode'                   : vdr( vtype='string', options=['live','dummy','simulation'] ),
        'force run mode'                      : vdr( vtype='string', options=['live','dummy','simulation'] ),
        'abort if any task fails'             : vdr( vtype='boolean', default=False ),
        'log resolved dependencies'           : vdr( vtype='boolean', default=False ),
        'job submission' : {
            'batch size'                      : vdr( vtype='integer', vmin=1, default=10 ),
            'delay between batches'           : vdr( vtype='integer', vmin=0, default=0  ),
            },
        'event handler submission' : {
            'batch size'                      : vdr( vtype='integer', vmin=1, default=10 ),
            'delay between batches'           : vdr( vtype='integer', vmin=0, default=0  ),
            },
        'poll and kill command submission' : {
            'batch size'                      : vdr( vtype='integer', vmin=1, default=10 ),
            'delay between batches'           : vdr( vtype='integer', vmin=0, default=0  ),
            },
        'lockserver' : {
            'enable'                          : vdr( vtype='boolean', default=False ),
            'simultaneous instances'          : vdr( vtype='boolean', default=False ),
            },
        'environment' : OrderedDict([
            ('__MANY__',                        vdr( vtype='string' )),
            ]),
        'event hooks' : {
            'startup handler'                 : vdr( vtype='string' ),
            'timeout handler'                 : vdr( vtype='string' ),
            'shutdown handler'                : vdr( vtype='string' ),
            'timeout'                         : vdr( vtype='float'  ),
            'reset timer'                     : vdr( vtype='boolean', default=True ),
            'abort if startup handler fails'  : vdr( vtype='boolean', default=False ),
            'abort if shutdown handler fails' : vdr( vtype='boolean', default=False ),
            'abort if timeout handler fails'  : vdr( vtype='boolean', default=False ),
            'abort on timeout'                : vdr( vtype='boolean', default=False ),
            },
        'simulation mode' : {
            'disable suite event hooks'       : vdr( vtype='boolean', default=True ),
            },
        'dummy mode' : {
            'disable suite event hooks'       : vdr( vtype='boolean', default=True ),
            },
        'accelerated clock' : { 
            'disable'                         : vdr( vtype='boolean', default=False ),
            'rate'                            : vdr( vtype='integer', default=10 ),
            'offset'                          : vdr( vtype='integer', default=24 ),
            },
        'reference test' : {
            'suite shutdown event handler'    : vdr( vtype='string', default='cylc hook check-triggering' ),
            'required run mode'               : vdr( vtype='string', options=[ 'live','simulation','dummy'] ),
            'allow task failures'             : vdr( vtype='boolean', default=False ),
            'expected task failures'          : vdr( vtype='string_list', default=[] ),
            'live mode suite timeout'         : vdr( vtype='float' ),
            'dummy mode suite timeout'        : vdr( vtype='float' ),
            'simulation mode suite timeout'   : vdr( vtype='float' ),
            },
        },
    'scheduling' : {
        'initial cycle time'                  : vdr(vtype='cycletime'),
        'final cycle time'                    : vdr(vtype='cycletime'),
        'cycling'                             : vdr(vtype='string', default="HoursOfTheDay" ),
        'runahead limit'                      : vdr(vtype='integer', vmin=0 ),
        'queues' : {
            'default' : {
                'limit'                       : vdr( vtype='integer', default=0),
                },
            '__MANY__' : {
                'limit'                       : vdr(vtype='integer', default=0 ),
                'members'                     : vdr(vtype='string_list', default=[]),
                },
            },
        'special tasks' : {
            'clock-triggered'                 : vdr(vtype='string_list', default=[]),
            'start-up'                        : vdr(vtype='string_list', default=[]),
            'cold-start'                      : vdr(vtype='string_list', default=[]),
            'sequential'                      : vdr(vtype='string_list', default=[]),
            'one-off'                         : vdr(vtype='string_list', default=[]),
            'explicit restart outputs'        : vdr(vtype='string_list', default=[]),
            'exclude at start-up'             : vdr(vtype='string_list', default=[]),
            'include at start-up'             : vdr(vtype='string_list', default=[]),
            },
        'dependencies' : {
            'graph'                           : vdr( vtype='string'),
            '__MANY__' :
            {
                'graph'                       : vdr( vtype='string'),
                'daemon'                      : vdr( vtype='string'),
                },
            },
        },
    'runtime' : {
        '__MANY__' : {
            'inherit'                         : vdr( vtype='string_list', default=[] ),
            'title'                           : vdr( vtype='string', default="No title provided" ),
            'description'                     : vdr( vtype='string', default="No description provided" ),
            'initial scripting'               : vdr( vtype='string' ),
            'environment scripting'           : vdr( vtype='string' ),
            'pre-command scripting'           : vdr( vtype='string' ),
            'command scripting'               : vdr( vtype='string', default='echo Default command scripting; sleep $(cylc rnd 1 16)'),
            'post-command scripting'          : vdr( vtype='string' ),
            'retry delays'                    : vdr( vtype='float_list', default=[] ),
            'manual completion'               : vdr( vtype='boolean', default=False ),
            'extra log files'                 : vdr( vtype='string_list', default=[] ),
            'enable resurrection'             : vdr( vtype='boolean', default=False ),
            'work sub-directory'              : vdr( vtype='string', default='$CYLC_TASK_ID' ),
            'submission polling intervals'    : vdr( vtype='float_list', default=[] ),
            'execution polling intervals'     : vdr( vtype='float_list', default=[] ),
            'simulation mode' :  {
                'run time range'              : vdr( vtype='integer_list', default=[1,16]),
                'simulate failure'            : vdr( vtype='boolean', default=False ),
                'disable task event hooks'    : vdr( vtype='boolean', default=True ),
                'disable retries'             : vdr( vtype='boolean', default=True ),
                },
            'dummy mode' : {
                'command scripting'              : vdr( vtype='string', default='echo Dummy command scripting; sleep $(cylc rnd 1 16)'),
                'disable pre-command scripting'  : vdr( vtype='boolean', default=True ),
                'disable post-command scripting' : vdr( vtype='boolean', default=True ),
                'disable task event hooks'       : vdr( vtype='boolean', default=True ),
                'disable retries'                : vdr( vtype='boolean', default=True ),
                },
            'job submission' : {
                'method'                      : vdr( vtype='string', default='background' ),
                'command template'            : vdr( vtype='string' ),
                'shell'                       : vdr( vtype='string',  default='/bin/bash' ),
                'retry delays'                : vdr( vtype='float_list', default=[] ),
                },
            'remote' : {
                'host'                        : vdr( vtype='string' ),
                'owner'                       : vdr( vtype='string' ),
                'suite definition directory'  : vdr( vtype='string' ),
                },
            'event hooks' : {
                'submitted handler'           : vdr( vtype='string' ),
                'started handler'             : vdr( vtype='string' ),
                'succeeded handler'           : vdr( vtype='string' ),
                'failed handler'              : vdr( vtype='string' ),
                'submission failed handler'   : vdr( vtype='string' ),
                'warning handler'             : vdr( vtype='string' ),
                'retry handler'               : vdr( vtype='string' ),
                'submission retry handler'    : vdr( vtype='string' ),
                'submission timeout handler'  : vdr( vtype='string' ),
                'submission timeout'          : vdr( vtype='float' ),
                'execution timeout handler'   : vdr( vtype='string' ),
                'execution timeout'           : vdr( vtype='float'),
                'reset timer'                 : vdr( vtype='boolean', default=False ),
                },
            'environment' : OrderedDict([
                ('__MANY__',                    vdr( vtype='string' )),
                ]),
            'directives' : OrderedDict([
                ('__MANY__',                    vdr( vtype='string' )),
                ]),
            'outputs' : {
                '__MANY__'                    : vdr( vtype='string' ),
                },
            },
        },
    'visualization' : {
        'initial cycle time'                  : vdr( vtype='integer' ),
        'final cycle time'                    : vdr( vtype='integer' ),
        'collapsed families'                  : vdr( vtype='string_list', default=[] ),
        'use node color for edges'            : vdr( vtype='boolean', default=True ),
        'use node color for labels'           : vdr( vtype='boolean', default=False ),
        'default node attributes'             : vdr( vtype='string_list', default=['style=unfilled', 'color=black', 'shape=box']),
        'default edge attributes'             : vdr( vtype='string_list', default=['color=black']),
        'enable live graph movie'             : vdr( vtype='boolean', default=False ),
        'node groups' : {
            '__MANY__'                        : vdr( vtype='string_list', default=[] ),
            },
        'node attributes' : {
            '__MANY__'                        : vdr( vtype='string_list', default=[] ),
            },
        'runtime graph' : {
            'enable'                          : vdr( vtype='boolean', default=False ),
            'cutoff'                          : vdr( vtype='integer', default=24 ),
            'directory'                       : vdr( vtype='string', default='$CYLC_SUITE_DEF_PATH/graphing'),
            },
        },
    'development' : {
        'disable task elimination'            : vdr( vtype='boolean', default=False ),
        },
    }

def get_expand_nonrt( fpath, template_vars, template_vars_file, do_expand=False, verbose=False ):
    global cfg
    if not cfg:
        cfg = parse( fpath, verbose, template_vars, template_vars_file )

        u = upgrader( cfg, SPEC, 'suite definition', verbose )
        u.deprecate( '5.2.0', ['cylc','event handler execution'], ['cylc','event handler submission'] )
        u.upgrade()

        validate( cfg, SPEC )

        # load non-runtime defaults
        for key,val in SPEC.items():
            if isinstance(val,dict) and key != 'runtime':
                if key not in cfg:
                    cfg[key] = {} # TODO - ordered dict?
                cfg[key] = expand( cfg[key], SPEC[key] )
    #print_nested(cfg)
    return cfg

def get_defaults_rt():
    return get_defaults( SPEC['runtime']['__MANY__'] )

