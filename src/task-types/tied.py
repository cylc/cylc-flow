#!/usr/bin/env python


from cycling import cycling
from pid import pid

class tied( pid, cycling ):
    # task class with previous instance dependence
    pass
