# THIS METHOD WAS REQUIRED FOR THE OLD, BROKEN, PURGE ALGORITHM; IT WILL
# PROBABLY NEVER BE NEEDED AGAIN.

# 1/ taken out of prerequisites.py:

    def will_satisfy_me( self, outputs ):
        # WILL outputs, WHEN COMPLETED, satisfy ANY of my prerequisites
        for label in self.get_not_satisfied_list():
            # for each of my unsatisfied prerequisites
            for output in outputs.satisfied: # NOTE: this can be T or F
                # compare it with each of the outputs
                if re.match( self.messages[label], output ):
                    return True
        return False

# 2/ taken out of prerequisites_fuzzy.py:

# TO DO: THINK ABOUT HOW FUZZY PREREQS AFFECT THIS FUNCTION:
#    def will_satisfy_me( self, outputs ):
#        # will another's outputs, if/when completed, satisfy any of my
#        # prequisites?
#
#        # this is similar to satisfy_me() but we don't need to know the most
#        # recent satisfying output message, just if any one can do it.
#
#        for prereq in self.satisfied.keys():
#            # for each of my prerequisites
#            if not self.satisfied[ prereq ]:
##                # if my prerequisite is not already satisfied
#
#                # extract cycle time from my prerequisite
#                m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
#                if not m:
#                    #log.critical( "FAILED TO MATCH MIN:MAX IN " + prereq )
#                    sys.exit(1)
#
#                [ my_start, my_minmax, my_end ] = m.groups()
#                [ my_min, my_max ] = my_minmax.split(':')
#
#                for output in outputs.satisfied.keys():
#
#                    # extract cycle time from other's output message
#                    m = re.compile( "^(.*)(\d{10})(.*)$").match( output )
#                    if not m:
#                        # this output can't possibly satisfy a
#                        # fuzzy; move on to the next one.
#                        continue
#
#                    [ other_start, other_ctime, other_end ] = m.groups()
#
#                    if other_start == my_start and other_end == my_end and other_ctime >= my_min and other_ctime <= my_max:
#                        self.sharpen_up( prereq, output )
