# -*- coding: utf-8 -*-

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

from __future__ import division,absolute_import
from django.views.generic import ListView,DetailView,CreateView,UpdateView,DeleteView
from django.forms import ModelForm
from rainman.models import History,Site
from irrigator.views import FormMixin,SiteParamMixin

class HistoryForm(ModelForm):
	class Meta:
		model = History
		exclude = ('site',)

	def save(self,commit=True):
		if hasattr(self,'site'):
			self.instance.site = self.site
		return super(HistoryForm,self).save(commit)


class HistoryMixin(FormMixin):
	model = History
	context_object_name = "history"
	def get_queryset(self):
		gu = self.request.user.get_profile()
		return super(HistoryMixin,self).get_queryset().filter(site__id__in=gu.sites.all()).order_by("-time")

class HistorysView(HistoryMixin,SiteParamMixin,ListView):
	context_object_name = "history_list"
	paginate_by = 50

class HistoryView(HistoryMixin,DetailView):
	def get_context_data(self,**k):
		ctx = super(HistoryView,self).get_context_data(**k)
		try:
			ctx['next_h'] = self.get_queryset().filter(time__gt=ctx['history'].time).order_by('time')[0]
		except IndexError:
			ctx['next_h'] = None
		try:
			ctx['prev_h'] = self.get_queryset().filter(time__lt=ctx['history'].time).order_by('-time')[0]
		except IndexError:
			ctx['prev_h'] = None
		return ctx
