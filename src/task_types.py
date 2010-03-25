#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from task_base import task_base
from mod_pid import pid
from mod_nopid import nopid

class forecast_model( pid, task_base ):
    # task class with previous instance dependence
    pass

class free_task( nopid, task_base ):
    # task class with no previous instance dependence
    pass
