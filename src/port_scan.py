#!/usr/bin/pyro

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import Pyro.errors
import cylc_pyro_client

# base (lowest allowed) Pyro socket number
pyro_base_port = 7766   # (7766 is the Pyro default)

# max number of sockets starting at base
pyro_port_range = 100 # (100 is the Pyro default)

def get_port( suite, owner, host ):
    found = False
    port = 0
    for p in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        try:
            one, two = cylc_pyro_client.ping( host, p )
        except Pyro.errors.ProtocolError:
            pass
        else:
            if one == suite and two == owner:
                found = True
                port = p
                break
    return ( found, port )    

def scan( host ):
    for port in range( pyro_base_port, pyro_base_port + pyro_port_range ):
        try:
            one, two = cylc_pyro_client.ping( host, port )
        except Pyro.errors.ProtocolError:
            pass
        else:
            print "Port " + str( port ) + ": suite " + one + ", owner " + two
