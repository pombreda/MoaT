#!/usr/bin/python
# -*- coding: utf-8 -*-

##
##  Copyright © 2007-2012, Matthias Urlichs <matthias@urlichs.de>
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU General Public License as published by
##  the Free Software Foundation, either version 3 of the License, or
##  (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##  GNU General Public License (included; see the file LICENSE)
##  for more details.
##

from __future__ import division,absolute_import,print_function

from homevent import patch;patch()
import rpyc
import sys
import gevent
from gevent import spawn
from gevent.queue import Queue
from rpyc.core.service import VoidService
from homevent import gevent_rpyc
from homevent.base import Name,flatten
from homevent.times import humandelta
from datetime import datetime
import signal
import os
import codecs
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

TESTING=os.environ.get("HOMEVENT_TEST",False)
gevent_rpyc.patch_all()

modes = "log,list,cmd".split(",")
from optparse import OptionParser
parser = OptionParser(conflict_handler="resolve")
parser.add_option("-h","--help","-?", action="help",
	help="print this help text")
parser.add_option("-s", "--server", dest="host", action="store",
	default="127.0.0.1", help="Server to connect to")
parser.add_option("-p", "--port", dest="port", action="store",
	type="int",default="50005", help="port to connect to")
parser.add_option("-6", "--ipv6", dest="ipv6", action="store_true",
	default=False, help="Use IPv6")

(opts, args) = parser.parse_args()

class ExitService(VoidService):
	def on_disconnect(self,*a,**k):
		sys.exit()

class Printer(object):
	def exposed_write(self,s):
		sys.stdout.write(s)

c = rpyc.connect(opts.host, opts.port, ipv6=opts.ipv6)#, service=ExitService)
#c._channel.stream.sock.settimeout(None)
c.root.stdout(Printer())

def main(c,opts,args):
	if not args:
		raise SyntaxError("set a mode (%s)" % (", ".join(modes),))
	mode = args[0]
	args = args[1:]

	if mode == "log":
		if args:
			raise SyntaxError("don't pass arguments")
		do_log(c)
	elif mode == "list":
		do_list(c,args)
	elif mode == "cmd":
		do_cmd(c,args)
	else:
		raise SyntaxError("mode not one of %s" % (",".join(modes),))

def do_log(c):
	q = Queue()
	sig = []

	def called(**k):
		try:
			if k["event"][-1] == "test" and k["event"][-2] == "motion":
				return
		except:
			pass
		for a,b in k.iteritems():
			print(a,b)
		for a,b in k["event"].ctx:
			print(a,b)
		print("")
		sys.stdout.flush()

	def q_called(**k):
		q.put((called,[],k))
	cb = c.root.monitor(q_called)

	def logged(level,*a):
		print(u"<%s> %s" % (level,u"¦".join((str(x) for x in a))))
		sys.stdout.flush()
	def q_logged(*a):
		q.put((logged,a,{}))
	cm = c.root.logger(q_logged,None,0)

	def do_shutdown(a,b):
		sig.append(True)
	signal.signal(signal.SIGINT,do_shutdown)
	signal.signal(signal.SIGTERM,do_shutdown)
	while not sig:
		p,a,k = q.get()
		p(*a,**k)
	c.close()

def do_cmd(c,args):
	if not args:
		raise SyntaxError("need an actual command, try 'help'")
	res = c.root.command(*args)

def do_list(c,args):
	def getter(q):
		if TESTING:
			now = c.root.now
		else:
			def now(x):
				return c.root.now()
		while True:
			res = q.get()
			if res is None:
				return
			p,t = res
			if isinstance(t,datetime):
				if TESTING and t.year != 2003:
					t = "%s" % (humandelta(t-now(t.year != 2003)),)
				else:
					t = "%s (%s)" % (humandelta(t-now(t.year != 2003)),t)
				if TESTING:
					lim = 3
				else:
					lim = 4
				ti = t.rfind('.')
				if ti>0 and len(t)-ti>lim and len(t)-ti<lim+6: # limit to msec
					t = t[:ti+lim]+")"

			print(p+u": "+unicode(t))

	def out_one(p,c):
		q = Queue(3)
		job = None
		try:
			job = spawn(getter,q)
			flatten(q,(c,),p)
		finally:
#					with log_wait("list "+str(event)):
			q.put(None)
			if job is not None:
				job.join()

	for x in c.root.cmd_list(*args):
		if x is None:
			print("(None?)")
			continue
			
		if len(x) == 2:
			a,b = x
			a = str(a)
			out_one(a,b)
#		if hasattr(b,"list"):
#			for bb in b.list():
#				print(a,bb)
#			continue
#		else:
#			print(a,b)
		else:
			if len(x) == 1 and isinstance(x[0],Name):
				x=str(x[0])
			print(x)
	

if __name__ == "__main__":
	try:
		main(c,opts,args)
	except SyntaxError as e:
		print(e)
	except Exception:
		raise
	except BaseException:
		pass
