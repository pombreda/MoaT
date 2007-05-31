#!/usr/bin/python
# -*- coding: utf-8 -*-

import homevent as h
import sys
from homevent.module import Loader,Unloader
from homevent.run import process_event

from test import run_logger
run_logger("modules")

load_ev = h.Event(h.Context(),"module","load","example")
unload_ev = h.Event(h.Context(),"module","unload","example")

h.register_worker(Loader())
h.register_worker(Unloader())

def main():
	d = h.process_event(load_ev)
	d.addCallback(lambda _: process_event(load_ev))
	d.addCallback(lambda _: process_event(unload_ev))
	d.addBoth(lambda _: h.shut_down())

h.mainloop(main)
