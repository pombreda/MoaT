# -*- coding: utf-8 -*-
"""\
	This module holds Twisted support stuff.
	"""

from twisted.internet.abstract import FileDescriptor
from twisted.internet import fdesc,defer,reactor
from posix import write
import sys

class StdInDescriptor(FileDescriptor):
	def fileno(self):
		return 0
	def doRead(self):
		try:
			fdesc.setNonBlocking(0)
			return fdesc.readFromFD(0, self.dataReceived)
		finally:
			fdesc.setBlocking(0)

class StdOutDescriptor(FileDescriptor):
	def fileno(self):
		return 1
	def writeSomeData(self, data):
		try:
			fdesc.setNonBlocking(1)
			return write(1,data)
		finally:
			fdesc.setBlocking(1)
	
def deferToLater(p,*a,**k):
	d = defer.Deferred()
	d.addCallback(lambda _: p(*a,**k))
	reactor.callLater(0,d.callback,None)
	return d