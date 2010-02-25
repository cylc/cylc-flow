#!/usr/bin/python

import sys
import subprocess

class job_submit:

    def __init__( owner ):

        self.owner = owner

    def construct_command( self ):
        self.command = 'sudo -u ' + self.owner + ' '
