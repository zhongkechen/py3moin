#!/usr/bin/env python

"""
FCKeditor - The text editor for Internet - http://www.fckeditor.net
Copyright (C) 2003-2010 Frederico Caldeira Knabben

== BEGIN LICENSE ==

Licensed under the terms of any of the following licenses at your
choice:

- GNU General Public License Version 2 or later (the "GPL")
http://www.gnu.org/licenses/gpl.html

- GNU Lesser General Public License Version 2.1 or later (the "LGPL")
http://www.gnu.org/licenses/lgpl.html

- Mozilla Public License Version 1.1 or later (the "MPL")
http://www.mozilla.org/MPL/MPL-1.1.html

== END LICENSE ==

Base Connector for Python (CGI and WSGI).

See config.py for configuration settings

"""
import os
import sys
from urllib.parse import parse_qs

from MoinMoin.web.http import parse_form_data

from fckcommands import *  # default command's implementation


class FCKeditorConnectorBase( object ):
	"The base connector class. Subclass it to extend functionality (see Zope example)"

	def __init__(self, environ=None):
		"Constructor: Here you should parse request fields, initialize variables, etc."
		self.request = FCKeditorRequest(environ) # Parse request
		self.headers = []						# Clean Headers
		if environ:
			self.environ = environ
		else:
			self.environ = os.environ

	# local functions

	def setHeader(self, key, value):
		self.headers.append ((key, value))
		return

class FCKeditorRequest:
	"A wrapper around the request object"
	def __init__(self, environ):
		if environ is None: # plain old CGI
			environ = dict(os.environ)
			environ['wsgi.input'] = getattr(sys.stdin, 'buffer', sys.stdin)
		self.environ = environ
		unused_stream, self.form, self.files = parse_form_data(environ)
		self.query = parse_qs(
			environ.get('QUERY_STRING', ''),
			keep_blank_values=True,
		)

	def has_key(self, key):
		return key in self

	def get(self, key, default=None):
		if key in self.files:
			field = self.files[key]
			field.file = field.stream
			return field
		if key in self.form:
			return self.form.get(key)
		if key in self.query:
			return self.query[key][0]
		return default

	def __contains__(self, key):
		return key in self.files or key in self.form or key in self.query
