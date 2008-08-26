""" 
A class that holds a list of 

PREREQUISITES,
  usually of the form "input file X required", or

POSTREQUISITES,
  usually of the form "output file Y completed" 
  
Each requisite is in a state of "satisfied" or "not satisfied".  
satisfied" state.
"""

class requisites:

    def __init__( self, reqs ):
        self.satisfied = {}
        self.ordered_list = reqs  
        for req in reqs:
            self.satisfied[req] = False

    def all_satisfied( self ):
        if False in self.satisfied.values(): 
            return False
        else:
            return True

    def is_satisfied( self, req ):
        if satisfied[ req ]:
            return True
        else:
            return False

    def set_satisfied( self, req ):
        self.satisfied[ req ] = True

    def set_all_satisfied( self ):
        for req in self.ordered_list:
            self.satisfied[ req ] = True

    def get_list( self ):
        return self.ordered_list

    def get_requisites( self ):
        return self.satisfied

    def satisfy_me( self, postreqs ):
        # can another's completed postreqs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for postreq in postreqs.satisfied.keys():
                    # compare it with each of the other's postreqs
                    if postreq == prereq and postreqs.satisfied[postreq]:
                        # if they match, my prereq has been satisfied
                        self.set_satisfied( prereq )

    def will_satisfy_me( self, postreqs ):
        # will another's postreqs, when completed, satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for postreq in postreqs.satisfied.keys():
                    # compare it with each of the other's postreqs
                    if postreq == prereq:
                        # if they match, my prereq has been satisfied
                        self.set_satisfied( prereq )
