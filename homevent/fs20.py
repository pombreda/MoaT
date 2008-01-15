# -*- coding: utf-8 -*-

##
##  Copyright © 2007-2008, Matthias Urlichs <matthias@urlichs.de>
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

from __future__ import division

"""\
This module is the basis for processing FS20 datagrams.
"""

from homevent.event import Event
from homevent.run import simple_event
from homevent.context import Context

from time import time

PREFIX_TIMESTAMP = 't'

PREFIX = {}

handlers = []
default_handler = None

class WrongDatagram(TypeError):
	"""The datagram could not be recognized"""
	pass

def to_hc(code, _len=8):
	"""convert a number to an n-digit 1234 value"""
	sft = 2*(_len-1)
	res = 0
	if isinstance(code,basestring):
		code = int(code)
	while True:
		res = 10*res + (((code >> sft) & 3) + 1)
		if not sft: break
		sft = sft-2
	return res

def from_hc(code, _len=8):
	"""convert an-digit 1234 value to a number"""
	res = 0
	sft = 0
	if isinstance(code,basestring):
		code = int(code)
	assert len(str(code)) == _len, "wrong format: "+str(code)
	while code:
		c = code % 10
		assert c >= 1 and c <= 5, "wrong form: "+str(code)
		res += (c - 1) << sft
		sft += 2
		code = code // 10
	return res

def to_dev(code):
	return to_hc(code, _len=4)
def from_dev(code):
	return from_hc(code, _len=4)
		

def register_handler(h):
	global default_handler
	if h in handlers:
		raise RuntimeError("Handler already registered: %s" % (h,))
	handlers.append(h)
	if default_handler is None:
		default_handler = h

def unregister_handler(h):
	global default_handler
	handlers.remove(h)
	if default_handler is h:
		try:
			default_handler = handlers[0]
		except IndexError:
			default_handler = None

class handler(object):
	"""\
	This abstract class defines the interface used to send and receive
	FS20-and-related datagrams. 
	"""
	def __init__(self,ctx=Context):
		self.last_timestamp = None
		self.ctx = ctx()
	
	def send(self, prefix, data):
		"""\
		Send this datagram.
		"""
		raise NotImplementedError("Dunno how to send datagrams")

	def datagramReceived(self, prefix, data, handler=None, timestamp=None):
		try:
			ext = PREFIX[prefix]
		except KeyError:
			simple_event(self.ctx, "fs20","unknown","prefix",prefix,"".join("%02x" % ord(x) for x in data))
		else:
			return ext.datagramReceived(self.ctx, data, handler, timestamp)


class recv_handler(object):
	"""Common handling for incoming datagrams"""
	last_timestamp = None
	last_data = None

	def dataReceived(self, ctx, data, handler=None, timedelta=None):
		raise NotImplementedError("You need to override 'dataReceived'!")

	def datagramReceived(self, ctx, data, handler=None, timestamp=None):
		if self.last_data is None or self.last_data != data:
			delta = None
			self.last_data = data
		else:
			if timestamp is None:
				timestamp = time()
			if self.last_timestamp:
				delta = timestamp - self.last_timestamp
			else:
				delta = None
		self.last_timestamp = timestamp

		return self.dataReceived(ctx, data, handler, delta)


