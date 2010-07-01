_________________________________________________+_D_E_S_C_R_I_P_T_I_O_N
Cylc scheduling demo for a simple UM-based forecast-analysis suite that
would normally be run by SCS, loosely based on NIWA's 2009 NZLAM suite.

_________________________________________________________+_S_T_A_R_T_U_P
1/ DUMMY MODE ONLY (no task scripts have been implemented).
2/ Cold starts can only be done at 06Z when the Met Office global model
   start dump is available to us.
______________________________________________________+_T_A_S_K__L_I_S_T
* g_gbl_cold  - get UM global dump for NZLAM coldstart        (06Z only)
* g_lbc_cold  - get LBC for the current cycle                 (06Z only)
* UM_nz_cold  - NZLAM coldstart forecast from global dump     (06Z only)

* g_obs       - get obstore files for the current cycle     (all cycles)
* g_bge       - get OPS bgerr file for the current cycle    (all cycles)
* g_lbc       - get LBC file for the *next two cycles*      (00 and 12Z)

* OPS1        - OPS processing for obs group 1              (all cycles)
* OPS2        - OPS processing for obs group 2              (all cycles)
* OPS3        - OPS processing for obs group 3              (all cycles)

* VAR         - Var analysis                                (all cycles)

* UM_nz       - NZLAM forecast                    (short f/c 00 and 12Z,
                                                    long f/c 06 and 18Z)

* post1       - nzlam long forecast post processing         (06 and 18Z)
* post2       - nzlam long forecast post processing         (06 and 18Z)

* arch        - archiving of NZLAM diagnostic output        (06 and 18Z)
