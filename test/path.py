#!/usr/bin/python
# -*- coding: utf-8 -*-

import homevent as h
from homevent.reactor import ShutdownHandler
from homevent.module import load_module
from test import run

input = """\
block:
	if exists path "..":
		log DEBUG Yes
	else:
		log DEBUG No1
	if exists path "...":
		log DEBUG No2
	else:
		log DEBUG Yes
	if exists directory "..":
		log DEBUG Yes
	else:
		log DEBUG No3
	if exists directory "README":
		log DEBUG No4
	else:
		log DEBUG Yes
	if exists file "README":
		log DEBUG Yes
	else:
		log DEBUG No5
	if exists file "..":
		log DEBUG No6
	else:
		log DEBUG Yes
shutdown
"""

h.main_words.register_statement(ShutdownHandler)
load_module("logging")
load_module("ifelse")
load_module("path")
load_module("block")

run("path",input)
