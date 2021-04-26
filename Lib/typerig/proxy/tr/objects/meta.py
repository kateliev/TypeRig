# MODULE: Typerig / Proxy / Metadata (Object)
# NOTE: Experimental proxy approach
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function

import fontlab as fl6
from typerig.core.objects.node import Node

# - Init ---------------------------------
__version__ = '0.1.0'

# - Classes -------------------------------
class Meta(object):
	''' Metadata object to dynamically connect to a host specified'''
	
	# - Metadata and proxy model
	__getter__ = '__getattribute__'
	__setter__ = '__setattr__'
	__host__ = 'self.host'
	__meta__ = {}

	# - Build and connect to host dynamically	
	for key, value in __meta__.items():
		exec("{dst} = property(lambda self: {host}.{get}('{src}'), lambda self, value: {host}.{set}('{src}', value))".format(host = __host__, src=value, dst=key, get=__getter__, set=__setter__))
		
	# - Initialize 
	def __init__(self, host_object):
		self.host = host_object

