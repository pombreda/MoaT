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

"""\
This part of the code defines what a (generic) worker is.

Briefly: a worker is something that recognizes an event and does
something about it.
"""

from __future__ import division,absolute_import

from homevent.context import Context
from homevent.event import Event,TrySomethingElse,NeverHappens
from homevent.base import Name,MIN_PRIO,MAX_PRIO,SYS_PRIO,SName
from homevent.times import humandelta, now
from homevent.twist import fix_exception,reraise,format_exception,log_wait
from gevent import spawn

#import os

def report_(err, verbose=False):
	"""A report wrapper which reports backtraces for exceptions"""
	if hasattr(err,"report"):
		for r in err.report():
			yield r
	elif not isinstance(err,BaseException):
		yield unicode(err)
	elif verbose and not getattr(err,"no_backtrace",False):
		from traceback import format_stack
		p = "ERROR: "
		for l in format_exception(err).rstrip("\n").split("\n"):
			yield p+l
			p="     : "
		if hasattr(err,"cmd"):
			yield "   at: "+cmd.file+":"+unicode(cmd.line)
		if hasattr(err,"within"):
			for w in err.within:
				p = "   in: "
				for r in w.report(verbose):
					yield p+r
					p = "     : "
		p = "   by: "
		for rr in format_stack():
			for r in rr.rstrip("\n").split("\n"):
				yield p+r
				p = "     : "
	else:
		yield "ERROR: "+unicode(err)

seqnum = 0

class WorkItem(object):
	u"""\
		One particular thing to do.

		*Everything* that this system does needs to be represented as a
		descendant of this class.

		This class itself is a dummy and does nothing, so you can use it
		to … well … do nothing.
		"""
	name = None
	prio = MIN_PRIO # not relevant here, but a required attribute
	id = 0
	call_count = 0
	last_call = None
	last_args = None

	def __init__(self):
		self._get_id()

	def _get_id(self):
		if not self.id:
			global seqnum
			seqnum += 1
			self.id = seqnum
		return self.id

	def process(self, **k):
		self.call_count += 1 
		self.last_call = now()
		self.last_args = k
	
	def report(self, verbose=False):
		if self.name:
			yield "WORK: "+self.name
		if self.id:
			yield "id: "+str(self.id)
		yield "call count: "+str(self.call_count)
		if self.last_call:
			yield "last call: %s (%s)" % (humandelta(now()-self.last_call),self.last_call)
		if self.last_args:
			for a,b in self.last_args.iteritems():
				yield "last %s: %s" % (a,b)

	def list(self):
		yield (unicode(self),)
		yield ("id",self.id)
		if hasattr(self,"event"):
			yield ("event",SName(self.event))
		if self.name:
			yield ("name",SName(self.name))
		yield ("call count",str(self.call_count))
		if self.last_call:
			yield ("last call",self.last_call)
		if self.last_args:
			for a,b in self.last_args.iteritems():
				yield ("last",a,b)
		for r in self.report(verbose=98):
			yield ("code",r)


	def __repr__(self):
		if self.id:
			return u"‹Item %d:%s›" % (self.id,self.name)
		return u"‹Item:%s›" % (self.name,)

	def __str__(self):
		return repr(self)


class WorkSequence(WorkItem):
	"""\ 
		A WorkSequence encapsulates things that are to be done in
		sequence. It recognizes the fact that some work takes time
		and allows for logging events without executing them.

		'event' and 'worker' are the events which caused this sequence
		to be generated.

		NB: This class is currently only instantiated via
		ConcurrentWorkSequence, below.
		"""
	in_step = None
	in_worker = None

	def __init__(self, event, worker):
		super(WorkSequence,self).__init__()
		self.work = []
		self.event = event
		self.worker = worker
#		if hasattr(event,"id"):
#			self.id = self.event.id
		if hasattr(event,"ctx"):
			self.ctx = event.ctx()
		else:
			self.ctx = Context()

		if isinstance(self.event,Event):
			en = SName(self.event)
		else:
			en = unicode(self.event)
		self.info = u"Worker %d for ‹%s›" % (self.id,en)

	def __repr__(self):
		if not hasattr(self,"work"):
			return u"‹%s:%d (?)›" % (self.__class__.__name__,self.id)
		return u"‹%s:%d (%d)›" % (self.__class__.__name__, self.id, len(self.work))
	
	def __str__(self):
		return repr(self)
	
	def append(self, w):
		if isinstance(w,SeqWorker):
			wn = w.process(event=self.event)
			if not isinstance(wn,WorkSequence):
				raise RuntimeError("%s: returned %s, not a WorkSequence" \
					% (w,wn))
			w = wn
		self.work.append(w)

	def process(self, **k):
		super(WorkSequence,self).process(**k)

		assert self.work,"empty workqueue in "+repr(self)
		self.in_step = step = 0
		self.in_worker = None
		res = None

		from homevent.logging import log_run,log_halted
		try:
			event = self.event
		except Exception as ex:
			fix_exception(ex)
			event = ex
		excepting = False

		for w in self.work:
			step += 1

			self.in_step = step
			self.in_worker = w
			r = None

			try:
				if not excepting or isinstance(w,ExcWorker):
					log_run(self,w,step)
					r = w.process(event=self.event, queue=self)
			except TrySomethingElse:
				pass
			except Exception as ex:
				fix_exception(ex)
				r = ex

			if isinstance(r,Exception):
				excepting = True
				if not hasattr(r,"within"):
					r.within=[w]
				r.within.append(self)
			if res is None:
				res = r
			elif isinstance(res,Exception):
				from homevent.logging import log_exc
				log_exc(msg="Unhandled nested exception", err=res)
				from homevent.run import process_failure
				process_failure(res)
				res = r

		if isinstance(res,Exception):
			reraise(res)

	def report(self, verbose=False):
		if not verbose:
			yield unicode(self) # +" for "+unicode(self.event)
			return

		if verbose > 2:
			v = verbose
		else:
			v = 1
		if verbose != 98:
			yield unicode(self)
			if self.work:
				prefix = "│  "
			else:
				prefix = "   "
			for r in super(WorkSequence,self).report(verbose):
				yield prefix+r
			if hasattr(self.event,"report"):
				for r in report_(self.event,False):
					yield prefix+r
			else:
				yield prefix+unicode(self.event)
		if self.worker:
			w="by "
			for r in self.worker.report(verbose):
				yield prefix+w+r
				w="   "

		pr = None
		step=1

		def pstep(a,b,c):
			if self.in_step and self.in_step == step:
				p_first = a+str(step)+"╕"
				p_mid = c+" "+u"│"
				p_last = c+" "+u"╵"
				p_single = a+" "+u"═"
				rep = pr.report(verbose-1)
			else:
				p_first = b+str(step)+u"╴"
				p_mid = c+"  "
				p_last = c+"  "
				p_single = b+str(step)+u"╴"
				rep = pr.report(v)
			rp=None

			pf=p_first
			pl=p_single
			for r in rep:
				if rp:
					yield pf+rp
					pf=p_mid
					pl=p_last
				rp=r
			if rp:
				yield pl+rp

		for w in self.work:
			if pr:
				for _ in pstep("╞","├","│"): yield _
				step += 1
			pr = w
		for _ in pstep("╘","└"," "): yield _

class ConcurrentWorkSequence(WorkSequence):
	"""\
		A work handler which runs all steps in parallel
		"""
	def process(self, **k):
		from homevent.logging import log_run,log_halted,log_exc

		super(WorkSequence,self).process(**k) ## this is intentional

		assert self.work,"empty workqueue in "+repr(self)
		event = self.event
		jobs = []

		def run(p,*a,**k):
			try:
				p(*a,**k)
			except TrySomethingElse:
				pass
			except Exception as exc:
				from homevent.logging import log_exc
				from homevent.run import process_failure
				fix_exception(exc)
				log_exc(msg="Unhandled exception", err=exc)
				process_failure(exc)

		for w in self.work:
			#log_run(self,w,0)
			j = spawn(run,w.process,event=self.event, queue=self)
			jobs.append(j)

		for j,w in zip(jobs,self.work):
			with log_wait("JobStop",w):
				j.join()


	def report(self, verbose=False):
		if not verbose:
			yield unicode(self) # +" for "+unicode(self.event)
			return

		if verbose > 2:
			v = verbose
		else:
			v = 1
		prefix = "   "
		if verbose != 98:
			yield unicode(self)
			for r in super(WorkSequence,self).report(verbose):
				yield prefix+r
			if hasattr(self.event,"report"):
				for r in report_(self.event,False):
					yield prefix+r
			else:
				yield prefix+unicode(self.event)
		if self.worker:
			w="by "
			for r in self.worker.report(verbose):
				yield prefix+w+r
				w="   "

		for w in self.work:
			p = u"➔ "
			for r in w.report(v):
				yield prefix+p+r
				p = u"  "

class Worker(WorkItem):
	"""\
		This is a generic worker. It accepts an event and does things to it.
		"""
	prio = (MIN_PRIO+MAX_PRIO)//2
	match_count = 0
	def __init__(self, name):
		"""\
			Initialize this worker.
			
			You need to pass a hopefully-unique name (in addition to any
			other arguments your subclass needs).
			"""
		super(Worker,self).__init__()
		self.name = name

	def list(self):
		for r in super(Worker,self).list():
			yield r
		yield ("matched",self.match_count)

	def __repr__(self):
		if not hasattr(self,"name"):
			return "%s(<uninitialized>)" % (self.__class__.__name__,)
		if self.id:
			return "%s(%d:%s)" % \
				(self.__class__.__name__, self.id,repr(self.name))
		else:
			return "%s(%s)" % \
				(self.__class__.__name__, repr(self.name))

	def __str__(self):
		return "=> %s:%s" % (self.__class__.__name__, self.name)
	def __unicode__(self):
		return u"⇒%s:%s" % (self.__class__.__name__, self.name)

	def report(self, verbose=False):
		yield "%s: %s" % \
			(self.__class__.__name__, self.name)
	
	def does_event(self, event):
		"""\
			Check if this worker can process that event.
			Do NOT actually do any work in this code!

			You need to override this.
			"""
		raise AssertionError("You need to override does_event()")
	
#	def process(self, **k):
#		"""\
#			Actually do the work on this event.
#
#			You need to override this. Don't forget to call super() first.
#			"""
#		super(Worker,self).process(**k)
#		raise AssertionError("%s: You need to override process()" % (self.__class__.__name__,))
	

class SeqWorker(Worker):
	"""\
		This worker will return a WorkSequence.
		Its process() code MUST NOT have any side effects!
		"""
	pass


class ExcWorker(Worker):
	"""\
		This worker will handle failures.
		does_failure() will be checked for original failures only.
		"""

	def does_failure(self,event):
		return False
	pass

class DoNothingWorker(Worker):
	def __init__(self):
		super(DoNothingWorker,self).__init__("no-op")
	def does_event(self,event):
		return True

import warnings
warnings.filterwarnings('ignore', message="returnValue.*", category=DeprecationWarning, lineno=242)

