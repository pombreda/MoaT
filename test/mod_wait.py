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

from homevent import patch;patch()
from homevent.reactor import ShutdownHandler
from homevent.module import load_module
from homevent.statement import main_words
from test import run

input = """\
async:
	wait Foo Bar: for 10
	trigger FooBar
wait X1: for 0.2
list wait
list wait Foo Bar
wait Foo Bar:
	for 0.1
	update
block:
	if exists wait Foo Baz:
		log ERROR No2
	else:
		log TRACE Yes
block:
	wait X2: for 0.2
	trigger DoNow $wait
wait X3: for 0.1
async:
	wait Foo Baz: until 8 min
	trigger Heya
wait: for 0.1
block:
	if exists wait Foo Baz:
		log TRACE Yes
	else:
		log ERROR No1
on whatever:
	var wait x Foo Baz
	log TRACE We wait $x
trigger whatever :sync
wait: for 0.3
del wait Foo Baz
block:
	if exists wait Foo Baz:
		log ERROR No3
	else:
		log TRACE Yes
wait: for 0.2
# observe no HeYa event
shutdown
"""

main_words.register_statement(ShutdownHandler)
load_module("trigger")
load_module("data")
load_module("wait")
load_module("block")
load_module("logging")
load_module("ifelse")
load_module("on_event")

run("wait",input)

