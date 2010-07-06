#!/usr/bin/pyro

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# Different cylc systems must register their Pyro objects under
# different "group names" in the Pyro Nameserver so that they don't 
# interfere with each other. 

# See the Pyro manual for nameserver hierachical naming details.
 
import os, re
import Pyro.naming, Pyro.errors

class ns:
    def __init__( self, hostname, username=os.environ['USER'] ):
        self.hostname = hostname

        self.rootgroup = ':cylc'

        # LOCATE THE PYRO NAMESERVER
        try:
            self.ns = Pyro.naming.NameServerLocator().getNS( self.hostname )
        except Pyro.errors.NamingError:
            raise SystemExit("Failed to find a Pyro Nameserver on " + self.hostname )

    def get_ns( self ): ########################################### NEEDED?
        return self.ns

    def registered( self, groupname ):
        if groupname in self.get_groups():
            return True
        else:
            return False

    def get_groups( self ):
        groups = {}
        # loop through registered objects
        for obj in self.ns.flatlist():
            # Extract the group name for each object (GROUP.name).
            # Note that GROUP may contain '.' characters too.
            # E.g. ':Default.ecoconnect.name'
            group = obj[0].rsplit('.', 1)[0]

            if re.match( ':cylc\.', group ):
                pass
                #group = re.sub( '^:cylc\.', '', group )
            else:
                continue

            if group not in groups.keys():
                groups[ group ] = 1
            else:
                groups[ group ] += 1

        return groups

    def print_info( self ):
        groups = self.get_groups()
        n_groups = len( groups.keys() )
        print "There are ", len( groups.keys() ), " groups registered with Pyro"
        for group in groups:
            print ' + ', group, ' ... (', groups[group], 'objects )'
