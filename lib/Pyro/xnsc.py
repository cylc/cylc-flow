#############################################################################
#
#	Pyro Name Server Control Tool with GUI 
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import sys, time
from Tkinter import *
from Pyro.naming import NameServerLocator
from Pyro.errors import NamingError, ConnectionClosedError
import Pyro.core

class xnscFrame(object):

	def quit(self):
		self.master.quit()

	def clearOutput(self):
		self.text_out.delete('1.0',AtEnd())
		self.outputln(time.asctime())

	def output(self,txt):
		self.text_out.insert(AtEnd(),txt)
		self.text_out.yview(AtEnd())

	def outputln(self,txt):
		self.output(txt+'\n')

	def b_clearoutput(self, event=None):
		self.clearOutput()

	def b_findNS(self,event=None):
		self.clearOutput()
		hst,prt = None,None
		self.authID = self.entry_AuthID.get()
		if event:
			# Pressed <return> in entry box
			addr = self.entry_NSloc.get().split(':')
			hst=addr[0]
			if len(addr)>1:
				prt=int(addr[1])
		# We need to keep the host/port for the shutdown button...
		self.NShost = hst
		self.NSport = prt
		self.outputln('*** finding NS')
		locator=NameServerLocator(identification=self.authID)
		bcaddr=self.entry_BCAddr.get().strip() or None
		try:
			self.NS=locator.getNS(hst,prt,trace=1,bcaddr=bcaddr)
			self.entry_NSloc.delete(0,AtEnd())
			self.entry_NSloc.insert(AtEnd(),self.NS.URI.address+':'+str(self.NS.URI.port))
			self.entry_AuthID.delete(0,AtEnd())
			self.entry_AuthID.insert(AtEnd(),'****')

			self.enable_buttons()
			self.outputln('   found, URI='+str(self.NS.URI))
		except:
			self.disable_buttons()
			self.outputln('   not found:');
			a,b = sys.exc_info()[:2]
			self.outputln('  '+str(a)+' : '+str(b))
			self.outputln('See standard output for trace messages.')
	
	def handle_comm_error(self,name):
		# Handle a communication error: disable buttons and print exception
		a,b = sys.exc_info()[:2]
		self.outputln('*** '+name+': exception occured:')
		self.outputln('  '+str(a)+' : '+str(b))
		if a==ConnectionClosedError:
			self.disable_buttons()
			self.outputln('*** Connection with NS lost - reconnect')
	
	def printError(self, msg, exc):
		line="## %s: " % msg
		if isinstance(exc.args, (list, tuple)):
			line+="; ".join(exc.args[:-1])
		else:
			line+=exc.args
		line+=" ##"
		self.outputln(line)
	
	def b_list(self,event=None):
		names = self.entry_arg.get().split()
		try:
			if names:
				self.outputln('*** List groups:')
				for n in names:
					self.output(' '+self.NS.fullName(n)+' --> ')
					try:
						self.printList(self.NS.list(n))
					except NamingError,x:
						self.printError("can't list",x)
			else:
				self.outputln('*** List default group:')
				self.printList(self.NS.list(None))
		except:
			self.handle_comm_error('list')
	def printList(self,lst):
		out='( '
		lst.sort()
		for (n,t) in lst:
			if t==0:
				out+='['+n+'] '
			elif t==1:
				out+=n+' '
		self.outputln(out+')')

	def b_listall(self,event=None):
		try:
			flat=self.NS.flatlist()
			flat.sort()
			self.outputln('--------- Flat dump of namespace')
			for (name,val) in flat:
				self.outputln(' '+name+' --> '+str(val))
			self.outputln('--------- End dump')
		except: 
			self.handle_comm_error('listall')
	
	def b_register(self,event=None):
		self.outputln('*** registering with NS:')
		try:
			(name,uri) = self.entry_arg.get().split()
			try:
				self.NS.register(name,uri)
				uri=Pyro.core.PyroURI(uri)
				self.outputln('  '+name+'  -->  '+str(uri))
			except NamingError,x:
				self.printError("Error from NS", x)
			except: 
				self.handle_comm_error('register')
		except ValueError:
			self.outputln('  Invalid arguments, use "<name> <URI>".')

	def b_resolve(self,event=None):
		self.outputln('*** resolving:')
		name=self.entry_arg.get()
		if not name:
			self.outputln('  Invalid arguments, use "<name>".')
		else:
			try:
				uri=self.NS.resolve(name)
				self.outputln('  '+name+'  -->  '+str(uri))
			except NamingError,x:
				self.printError("can't resolve '"+name+"'", x)
			except: 
				self.handle_comm_error('resolve')
	
	def b_remove(self,event=None):
		self.outputln('*** removing:')
		name=self.entry_arg.get()
		if not name:
			self.outputln('  Invalid arguments, use "<name>".')
		else:
			try:
				self.NS.unregister(name)
				self.outputln('*** removed: '+name)
			except NamingError,x:
				self.printError("Can't remove '"+name+"'", x)
			except: 
				self.handle_comm_error('remove')
	
	def b_ping(self,event=None):
		try:
			self.NS.ping()
			self.outputln('*** ping NS: up and running!')
		except: 
			self.handle_comm_error('ping')
	
	def b_creategroup(self,event=None):
		name=self.entry_arg.get()
		if not name:
			self.outputln('  Invalid arguments, use "<name>".')
		else:
			try:
				self.NS.createGroup(name)
				self.outputln('*** group created: '+name)
			except Exception,x:
				self.printError("Can't create group",x)
	
	def b_deletegroup(self,event=None):
		name=self.entry_arg.get()
		if not name:
			self.outputln('  Invalid arguments, use "<name>".')
		else:
			try:
				self.NS.deleteGroup(name)
				self.outputln('*** group deleted: '+name)
			except Exception,x:
				self.printError("Can't delete group",x)

	def b_showmeta(self,event=None):
		name=self.NS.fullName(self.entry_arg.get())
		self.outputln('*** showing meta info of: '+name)
		try:
			self.outputln("system meta info : "+str(self.NS._getSystemMeta(name)))
			self.outputln("  user meta info : "+str(self.NS.getMeta(name)))
		except NamingError,x:
			self.printError("Can't get Meta info",x)
		except: 
			self.handle_comm_error('showmeta')
		
	def b_setmeta(self,event=None):
		self.outputln('*** setting user meta data:')
		try:
			(name,meta) = self.entry_arg.get().split(None,1)
			try:
				self.NS.setMeta(name,meta)
				self.outputln('  '+name+'  META='+meta)
			except NamingError,x:
				self.printError("Error from NS", x)
			except: 
				self.handle_comm_error('setmeta')
		except ValueError:
			self.outputln('  Invalid arguments, use "<name> <metadata>".')

	def b_resync(self,event=None):
		self.outputln("*** resync NS with twin")
		try:
			self.NS.resync()
		except NamingError,x:
			self.printError("Can't resync",x)
		except: 
			self.handle_comm_error('resync')

	def b_shutdown(self,event=None):
		locator = NameServerLocator(self.authID)
		try:
			result = locator.sendSysCommand('shutdown',self.NShost,self.NSport,0)
			self.outputln('*** The NS replied to the shutdown message: '+str(result))
		except:
			self.disable_buttons()
			self.outputln('   not found:');
			a,b = sys.exc_info()[:2]
			self.outputln('  '+str(a)+' : '+str(b))
			
	def enable_buttons(self):
		self.enable_disable_buttons(NORMAL)
		
	def disable_buttons(self):
		self.enable_disable_buttons(DISABLED)

	def enable_disable_buttons(self,state):
		self.but_ping['state']=state
		self.but_list['state']=state
		self.but_listall['state']=state
		self.but_resolve['state']=state
		self.but_register['state']=state
		self.but_remove['state']=state
		self.but_shutdown['state']=state
		self.but_showmeta['state']=state
		self.but_setmeta['state']=state
		self.but_resync['state']=state
		self.but_creategroup['state']=state
		self.but_deletegroup['state']=state

	def createWidgets(self):
		frame_top = Frame(self.master,borderwidth=2,relief=GROOVE)
		frame_top1 = Frame(frame_top,borderwidth=0)
		Label(frame_top1,text='Name Server Location (host:port)').pack(side=LEFT,anchor=W)
		self.entry_NSloc=Entry(frame_top1)
		self.entry_NSloc.bind('<Return>',self.b_findNS)
		self.entry_NSloc.pack(expand=1,fill=X,side=LEFT)
		Label(frame_top1,text='(press enter)').pack(side=LEFT,anchor=W)
		frame_top1.pack(fill=X)
		frame_top2 = Frame(frame_top,borderwidth=0)
		frame_top3 = Frame(frame_top,borderwidth=0)
		Label(frame_top2,text='Authorization ID:').pack(side=LEFT,anchor=W)
		self.entry_AuthID=Entry(frame_top2)
		self.entry_AuthID.bind('<Return>',self.b_findNS)
		self.entry_AuthID.pack(expand=1,fill=X,side=LEFT)
		Label(frame_top3,text='Broadcast address:').pack(side=LEFT,anchor=W)
		self.entry_BCAddr=Entry(frame_top3)
		self.entry_BCAddr.pack(expand=1,fill=X,side=LEFT)
		self.but_findNS=Button(frame_top3,text='Auto Discover NS',command=self.b_findNS)
		self.QUIT=Button(frame_top3,text='QUIT',command=self.quit)
		self.QUIT.pack(side=RIGHT)
		self.but_findNS.pack(side=RIGHT)
		frame_top2.pack(fill=X)
		frame_top3.pack(fill=X)
		frame_top.pack(fill=X)
		
		frame_cmds=Frame(self.master)
		frame_cmds1=Frame(frame_cmds)
		frame_cmds2=Frame(frame_cmds)
		self.but_ping=Button(frame_cmds1,text='Ping',state=DISABLED,command=self.b_ping)
		self.but_list=Button(frame_cmds1,text='List',state=DISABLED,command=self.b_list)
		self.but_listall=Button(frame_cmds1,text='List All',state=DISABLED,command=self.b_listall)
		self.but_register=Button(frame_cmds2,text='Register',state=DISABLED,command=self.b_register)
		self.but_resolve=Button(frame_cmds1,text='Resolve',state=DISABLED,command=self.b_resolve)
		self.but_remove=Button(frame_cmds2,text='Remove',state=DISABLED,command=self.b_remove)
		self.but_creategroup=Button(frame_cmds2,text='Create Group',state=DISABLED,command=self.b_creategroup)
		self.but_deletegroup=Button(frame_cmds2,text='Delete Group',state=DISABLED,command=self.b_deletegroup)
		self.but_showmeta=Button(frame_cmds1,text='Show Meta',state=DISABLED,command=self.b_showmeta)
		self.but_setmeta=Button(frame_cmds1,text='Set Meta',state=DISABLED,command=self.b_setmeta)
		self.but_resync=Button(frame_cmds1,text='ReSync',state=DISABLED,command=self.b_resync)
		self.but_shutdown=Button(frame_cmds1,text='Shutdown',state=DISABLED,command=self.b_shutdown)
		self.but_clearoutput=Button(frame_cmds2,text='Clear output',command=self.b_clearoutput)
		Label(frame_cmds,text='NS commands:').pack(side=LEFT)
		self.but_ping.pack(side=LEFT)
		self.but_list.pack(side=LEFT)
		self.but_listall.pack(side=LEFT)
		self.but_register.pack(side=LEFT)
		self.but_resolve.pack(side=LEFT)
		self.but_remove.pack(side=LEFT)
		self.but_creategroup.pack(side=LEFT)
		self.but_deletegroup.pack(side=LEFT)
		self.but_showmeta.pack(side=LEFT)
		self.but_setmeta.pack(side=LEFT)
		self.but_resync.pack(side=LEFT)
		self.but_shutdown.pack(side=LEFT)
		self.but_clearoutput.pack(side=RIGHT)

		frame_args=Frame(self.master,borderwidth=2)
		self.entry_arg=Entry(frame_args)
		Label(frame_args,text='Command arguments').pack(side=LEFT)
		self.entry_arg.pack(expand=1,fill=X)
		
		frame_output=Frame(self.master)
		ys=Scrollbar(frame_output,orient=VERTICAL)
		self.text_out=Text(frame_output,yscrollcommand=ys.set,width=90,height=20)
		ys['command']=self.text_out.yview
		ys.pack(fill=Y,side=LEFT)
		self.text_out.pack(side=LEFT,expand=1,fill=BOTH)

		# pack root children:
		frame_cmds1.pack(fill=X)
		frame_cmds2.pack(fill=X)
		frame_cmds.pack(fill=X)
		frame_args.pack(fill=X)
		frame_output.pack(fill=BOTH,expand=1)

	def __init__(self, master=None):
		self.master = master	
		self.createWidgets()

def main(argv):
	Pyro.core.initClient()
	root=Tk()
	root.title('xnsc - Pyro Name Server control tool - Pyro version '+Pyro.constants.VERSION)
	app=xnscFrame(root)
	root.protocol('WM_DELETE_WINDOW',root.quit)
	root.mainloop()

# allow easy usage with python -m
if __name__=="__main__":
	import sys
	main(sys.argv)
