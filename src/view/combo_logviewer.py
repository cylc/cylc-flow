from tailer import tailer
import gtk
import pygtk
####pygtk.require('2.0')
import time, os, re, sys

from logviewer import logviewer

class combo_logviewer( logviewer ):
 
    def __init__( self, name, file_list ):
        self.file_list = file_list
        file = os.path.basename( file_list[0] )
        dir = os.path.dirname( file_list[0] )
        logviewer.__init__( self, name, dir, file )

    def create_gui_panel( self ):
        logviewer.create_gui_panel( self )
        
        combobox = gtk.combo_box_new_text()
        combobox.append_text( 'Select File' ) 
        for file in self.file_list:
            combobox.append_text( os.path.basename( file ) )

        combobox.connect("changed", self.switch_log )
        combobox.set_active(0)

        self.hbox.pack_end( combobox, False )

    def switch_log( self, cb ):
        model = cb.get_model()
        index = cb.get_active()
        if index == 0:
            return False

        file = model[index][0]
        for F in self.file_list:
            if os.path.basename( F ) == file:
                self.replace_log( F )
                break

        return False

    def replace_log( self, file ):
        self.file = os.path.basename( file )
        self.dir = os.path.dirname( file )
        self.t.quit = True
        logbuffer = self.logview.get_buffer()
        s,e = logbuffer.get_bounds()
        self.reset_logbuffer()
        logbuffer.delete( s, e )
        #self.log_label.set_text( self.path() ) 
        self.t = tailer( self.logview, self.path() )
        ###print "Starting log viewer thread"
        self.t.start()
