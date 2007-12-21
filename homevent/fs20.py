# -*- coding: utf-8 -*-

"""\
This module is the basis for processing FS20 datagrams.
"""

from homevent.event import Event
from homevent.run import process_event,process_failure

groups = {}
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
	FS20 datagrams. 
	"""
	def __init__(self):
		pass
	
	def send(self, data):
		"""\
		Send this datagram.
		"""
		raise NotImplementedError("Dunno how to send datagrams")

	def datagramReceived(self, data, handler=None):
		qs = 0
		for d in data:
			qs += ord(d)
		qs -= ord(data[-1]) # the above loop added it, that's nonsense
		qs = (ord(data[-1]) - qs) & 0xFF # we want the actual difference

		code = ord(data[0])*256+ord(data[1])
		try:
			g = groups[(code,qs)]
		except KeyError:
			process_event(Event(self.parent.ctx, "fs20","unknown",to_hc(code),qs,"".join("%02x" % ord(x) for x in data))).addErrback(process_failure)
			
		else:
			return g.datagramReceived(data[2:-1], handler)
	

class group(object):
	"""\
	This abstract class represents a group of FS20 devices.
	A group is defined by a common house code and checksum offset.
	"""

	handler = None

	def __init__(self, code, qsum):
		self.code = code
		self.qsum = qsum
		code = (code, qsum)
		if code in groups:
			raise RuntimeError("House code %04x already known" % (code,))
		groups[code] = self
	
	def delete(self):
		del groups[(self.code, self.qsum)]

	def datagramReceived(self, data, handler=None):
		raise NotImplementedError("Dunno how to process incoming datagrams")

	def send(self, data, handler=None):
		import sys; print >>sys.stderr,"SENDIT",repr(data)
		if handler is None:
			handler = self.handler or default_handler

		data = chr(self.code >> 8) + chr(self.code & 0xFF) + data
		qsum = self.qsum
		for c in data:
			qsum += ord(c)
		data += chr(qsum & 0xFF)

		import sys; print >>sys.stderr,"SEND BY",repr(handler)
		return handler.send(data)

