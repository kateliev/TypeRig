# MODULE: TypeRig / Core / Atom (Objects)
# NOTE: Assorted atomic, generic objects
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2021	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.collection import CustomList

# - Init -------------------------------
__version__ = '0.0.8'

# - Objects ----------------------------
class Member(object):
	''' A primitive that is a member of a sequence. '''
	def __init__(self, *args, **kwargs):
		self.parent = kwargs.get('parent', None)

	# - Properties -----------------------	
	@property
	def index(self):
		return self.parent.index(self)
	
	@property
	def next(self):
		try:
			return self.parent[self.index + 1]
		
		except (IndexError, AttributeError) as error:
			if self.index == len(self.parent) - 1:
				return self.parent[0]

			return None
	
	@property
	def prev(self):
		try:
			return self.parent[self.index - 1]
		
		except (IndexError, AttributeError) as error:
			if self.index == 0:
				return self.parent[-1]

			return None

class Container(CustomList, Member):
	''' A primitive that is a member of a sequence and seqence of its own. '''
	def __init__(self, data=None, **kwargs):
		self.data = []
		self.parent = kwargs.get('parent', None)
		self.locked = kwargs.get('locked', False)
		self.__subclass__ = kwargs.get('default_factory', self.__class__)

		if data is not None:
			if type(data) == type(self.data):
				self.data[:] = data
			elif isinstance(data, self.__class__):
				self.data[:] = data.data[:]
			else:
				self.data = list(data)

		if len(self.data):
			for idx in range(len(self.data)):
				if isinstance(self.data[idx], self.__subclass__):
					self.data[idx].parent = self
				
				elif isinstance(self.data[idx], (tuple, list)):
					self.data[idx] = self.__subclass__(self.data[idx], parent=self)

	# - Methods ------------------------
	def append(self, item):
		if not self.locked:
			if isinstance(item, self.__subclass__):
				item.parent = self
			else:
				item = self.__subclass__(item, parent=self)

			self.data.append(item)

class Linker(object):
	''' Doubly-linked-list primitive. '''
	def __init__(self, data, **kwargs):
		self.data = data
		self.parent = kwargs.get('parent', None)
		self.next = kwargs.get('next', None)
		self.prev = kwargs.get('prev', None)
		self.start = kwargs.get('start', False)

	def __add__(self, other):
		if isinstance(other, self.__class__):
			if isinstance(self.next, self.__class__):
				temp_link = self.next
				temp_link.prev = other
				other.next = temp_link
				self.next = other

			elif self.next is None:
				self.next = other

			return self

	def __sub__(self, other):
		if isinstance(other, self.__class__) and self.next == other:
			temp_link = self.next.next
			temp_link.prev = self
			self.next = temp_link

			return self

	def __iter__(self):
		curr_link = self

		while curr_link is not None: # and not curr_link.next.start:
			yield curr_link
			
			curr_link = curr_link.next

	def __repr__(self):
		return str(self.data)

	# - Functions ------------------
	def where(self, search, value):
		curr_link = self

		while curr_link is not None:
			if eval('curr_link.{}{}'.format(search, value)):
				yield curr_link
			
			curr_link = curr_link.next

if __name__ == "__main__":
	from operator import add

	p = []
	am = Member((10,10), parent=p)
	bm = Member((20,10), parent=p)
	p.append(am)
	p.append(bm)
	print(am.index)
	print(am.next)

	a = Linker((10,10))
	b = Linker((20,10))
	c = Linker((30,10))
	a + b + c
	print(a.next)

	ac = Container((10,10))
	bc = Container((20,10))
	cc = Container((30,10))
	dc = Container([ac, bc, cc, (20,30)])
	print(cc.next.next)


