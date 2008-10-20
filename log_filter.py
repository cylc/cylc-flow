#!/usr/bin/python

import logging

class LogFilter(logging.Filter):
    # replace log message timestamps with dummy clock times

    def __init__(self, dclock, name = "" ):
        logging.Filter.__init__( self, name )
        self.dummy_clock = dclock

    def filter(self, record):
        # replace log message time stamp with dummy time
        record.created = self.dummy_clock.get_epoch()
        return True
