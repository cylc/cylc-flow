from logview import tailer
import gtk
import pygtk
####pygtk.require('2.0')
import time, os, re, sys
from warning_dialog import warning_dialog

from logviewer import logviewer

class cylc_logviewer( logviewer ):
 
    def __init__( self, name, dir, file, task_list ):
        self.task_list = task_list
        logviewer.__init__( self, name, dir, file )


    def create_gui_panel( self ):
        logviewer.create_gui_panel( self )
        
        combobox = gtk.combo_box_new_text()
        combobox.append_text( 'Select Log' ) 
        combobox.append_text( 'main' ) 
        for task in self.task_list:
            combobox.append_text( task )

        combobox.connect("changed", self.switch_log )
        combobox.set_active(0)

        previous = gtk.Button( "newer rotation" )
        previous.connect("clicked", self.rotate_log, False )
        self.hbox.pack_end( previous, False )

        previous = gtk.Button( "older rotation" )
        previous.connect("clicked", self.rotate_log, True )
        self.hbox.pack_end( previous, False )

        self.hbox.pack_end( combobox, False )


    def switch_log( self, cb ):
        model = cb.get_model()
        index = cb.get_active()
        if index == 0:
            return False

        task = model[index][0]
        self.replace_log( task )

        return False

    def rotate_log( self, bt, go_older ):
        cur_log = self.file
        m = re.match( '(.*)\.(\d)$', cur_log ) 
        if m:
            level = int( m.groups()[1] )
            log_base = m.groups()[0]
        else:
            level = 0
            log_base = cur_log

        warn = False

        if go_older:
            level += 1
        else:
            level -= 1

        if level < 0:
            warning_dialog( "The newest (active) log is already displayed" ).warn()
            return

        if level == 0:
            new_log = log_base
        else:
            new_log = log_base + '.' + str( level )

        if new_log not in os.listdir( self.dir ):
            print new_log
            warning_dialog( "No older log available" ).warn()
            return

        self.replace_log( new_log )

    def replace_log( self, file ):
        self.file = file
        self.t.quit = True
        logbuffer = self.logview.get_buffer()
        s,e = logbuffer.get_bounds()
        self.reset_logbuffer()
        logbuffer.delete( s, e )
        self.log_label.set_text( self.path() ) 
        self.t = tailer( self.logview, self.path() )
        print "Starting log viewer thread"
        self.t.start()


