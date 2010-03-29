
________________________________________________________________+_I_N_F_O
cylc scheduling demo for a simple um-based forecast-analysis suite that
would normally be run by scs, loosely based on niwa's nzlam 3d var suite
circa 2009. 

____________________________________________+_D_U_M_M_Y__M_O_D_E__O_N_L_Y
but: could easily write system scripts a la userguide example systems.

_______________________________________________________+_T_A_S_K__L_I_S_T
* g_gbl_cold      - get downloaded UM global dump for NZLAM coldstart
* g_lbc_cold      - get downloaded LBC for the current cycle 

* g_obs           - get downloaded obstore files for the current cycle
* g_bge           - get downloaeded OPS bgerr file for the current cycle
* g_lbc           - get downloaded LBC file for the *next two cycles*
                    runs in the 00 and 12 cycles only.

* UM_nz_cold      - NZLAM coldstart forecast from UM global dump 

* OPS1            - OPS processing for obs group 1
* OPS2            - OPS processing for obs group 2
* OPS3            - OPS processing for obs group 3

* VAR             - 3D-Var analysis

* UM_nz           - NZLAM forecast (short run at 00,12; long at 06,18Z)

* post            - post process NZLAM diagnostic output, all cycles
* post2           - extra post processing, only at 06 and 18 UTC

* arch            - archiving of NZLAM diagnostic output
