# -*- coding: utf-8 -*-

##
##  Copyright © 2012, Matthias Urlichs <matthias@urlichs.de>
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
		Recalculate valves.
		"""

from django.core.management.base import BaseCommand, CommandError
from rainman.models import Site,Valve,Schedule,Controller,History,Level
from datetime import datetime,time,timedelta
from django.db.models import F,Q
from django.utils.timezone import utc,get_current_timezone
from optparse import make_option


class Command(BaseCommand):
	args = '<valve>…'
	help = 'Fix calculated water levels'

	option_list = BaseCommand.option_list + (
			make_option('-s','--site',
				action='store',
				dest='site',
				default=None,
				help='Select the site to use'),
			make_option('-c','--controller',
				action='store',
				dest='controller',
				default=None,
				help='Select the controller to use'),
			make_option('-f','--feed',
				action='store',
				dest='feed',
				default=None,
				help='Select the water feed to use'),
			make_option('-a','--age',
				action='store',
				type=float,
				dest='age',
				default=7,
				help='Start n days in the past'),
			make_option('-n','--no-save',
				action='store_false',
				dest='save',
				default=True,
				help="don't save"),
			make_option('-V','--verbose',
				action='store_true',
				dest='verbose',
				default=False,
				help="be more chatty"),
			)

	def handle(self, *args, **options):
		q = Q()
		if options['site']:
			q &= Q(controller__site__name=options['site'])
		if options['controller']:
			q &= Q(controller__name=options['controller'])
		if options['feed']:
			q &= Q(feed__name=options['feed'])
		if len(args):
			for a in args:
				v = Valve.objects.get(q & Q(name=a))
				self.one_valve(v, options)
		else:
			for v in Valve.objects.filter(q):
				self.one_valve(v,options)

	def one_valve(self,v,options):
		if options['verbose']:
			print "Updating",v
		params = ParamGroup(v.param_group)
		now = datetime.utcnow().replace(tzinfo=utc)
		start=now-timedelta(options['age'])
		hist = list(History.objects.filter(site=v.controller.site,time__gte=start).order_by("-time"))
		level=None
		ts=None
		s = v.controller.site

		for lv in Level.objects.filter(valve=v).order_by("time"):
			if level is None:
				level=lv.level
				ts=lv.time
				continue
			sum_f=0
			sum_r=0
			while hist:
				if hist[-1].time > lv.time:
					break
				h=hist.pop()
				f = params.env_factor(h,options['verbose'])
				add_f = v.shade*s.db_rate*params.pg.factor*f*(h.time-ts).total_seconds()
				add_r = v.runoff*h.rain
				if options['verbose']:
					print "Apply",h,f,u"– dry="+str(add_f)," rain="+str(add_r)
					print "    T:",h.temp,"W:",h.wind,"S:",h.sun
				sum_f += add_f
				sum_r += add_r
				ts=h.time

			level += sum_f
			if (lv.flow > 0 or sum_r > 0) and level > v.max_level:
				level = v.max_level
			level -= sum_r+lv.flow/v.area

			if options['verbose']:
				print "Updated",lv,"from",lv.level,"to",level
				print "   evaporate="+str(sum_f),"rain="+str(sum_r),"water="+str(lv.flow/v.area)
			if options['save']:
				lv.level = level
				lv.save()
		print "Updated",v,"from",v.level,"to",level
		if options['save']:
			v.level=level
			v.save()


class ParamGroup(object):
	"""For now, a copy from runschedule"""
	env_cache = None

	def __init__(self,pargroup):
		self.env_cache = {}
		self.pg = pargroup

	def log(self,txt):
		log(self.pg.site,"ParamGroup "+self.pg.name+": "+txt)

	def sync(self):
		pass
	def refresh(self):
		self.env_cache = {}
	def shutdown(self):
		pass

	def env_factor(self,h,logging):
		if logging:
			def logger(x):
				print x
		else:
			logger = None
		return self.pg.env_factor(h,logger)
