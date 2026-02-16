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
import copy, uuid

from typerig.core.objects.collection import CustomList

# - Init -------------------------------
__version__ = '0.3.0'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Objects ----------------------------
class Atom(object):
	'''Sentinel'''
	__slots__ = ()

	def __init__(self, *args, **kwargs):
		pass

class Navigable(object):
	'''Mixin for objects that navigate within a parent sequence.
	Requires self.parent to be defined by the inheriting class.'''
	__slots__ = ()

	@property
	def idx(self):
		return self.parent.index(self)
	
	@property
	def next(self):
		try:
			return self.parent[self.idx + 1]
		
		except (IndexError, AttributeError):
			if self.idx == len(self.parent) - 1:
				return self.parent[0]

			return None
	
	@property
	def prev(self):
		try:
			return self.parent[self.idx - 1]
		
		except (IndexError, AttributeError):
			if self.idx == 0:
				return self.parent[-1]

			return None

class Member(Navigable, Atom):
	''' A primitive that is a member of a sequence. '''
	__slots__ = ('uid', 'identifier', 'parent', 'lib')

	def __init__(self, *args, **kwargs):
		self.uid = uuid.uuid4()
		self.parent = kwargs.pop('parent', None)
		self.identifier = kwargs.get('identifier', None)

	# - Internals -----------------------
	def __hash__(self):
		return hash(self.uid)

	# - Functions ----------------------
	def clone(self):
		return copy.deepcopy(self)

class Container(CustomList, Navigable, Atom):
	''' A primitive that is a member of a sequence and sequence of its own. '''
	__slots__ = ('data', 'uid', 'identifier', 'parent', 'lib', '_lock', '_subclass')

	def __init__(self, data=None, **kwargs):
		super(Container, self).__init__(data, **kwargs)

		# - Init
		self.uid = uuid.uuid4()
		self.parent = kwargs.pop('parent', None)
		self._lock = kwargs.pop('locked', False)
		self._subclass = kwargs.pop('default_factory', self.__class__)

		# - Process data
		if len(self.data):
			for idx in range(len(self.data)):
				self.data[idx] = self._coerce(self.data[idx])
				
	# - Internals ----------------------
	def __hash__(self):
		return hash(self.uid)

	def __getitem__(self, i):
		# -- Lazy coercion on access (strict: coerces everything)
		if not isinstance(self.data[i], self._subclass):
			self.data[i] = self._subclass(self.data[i], parent=self)

		return self.data[i]

	def __setitem__(self, i, item): 
		if not isinstance(item, self._subclass):
			item = self._subclass(item, parent=self)

		self.data[i] = item

	def __repr__(self):
		return '<{}: {}>'.format(self.__class__.__name__, repr(self.data))

	# - Methods ------------------------
	def _coerce(self, item):
		'''Coerce item to _subclass if needed, set parent.
		Primitives (int, float, basestring) pass through unchanged.'''
		if isinstance(item, self._subclass):
			item.parent = self
			return item

		if not isinstance(item, (int, float, basestring)):
			return self._subclass(item, parent=self)

		return item

	def _collect(self, attr):
		'''Collect attribute from all children into a flat list.'''
		result = []

		for child in self.data:
			value = getattr(child, attr, None)

			if value is not None:
				if isinstance(value, (list, tuple)):
					result += list(value)
				else:
					result.append(value)

		return result

	@classmethod
	def as_proxy(cls, data=None, **kwargs):
		'''Create a lightweight proxy instance (skips metadata init).'''
		kwargs['proxy'] = True
		return cls(data, **kwargs)

	def insert(self, i, item):
		if not self._lock:
			self.data.insert(i, self._coerce(item))

	def pop(self, i=-1): 
		if not self._lock:
			item = self.data[i]

			if isinstance(item, self._subclass):
				item.parent = None

			return self.data.pop(i)

		return None

	def append(self, item):
		if not self._lock:
			self.data.append(self._coerce(item))

	# - Functions ----------------------
	def clone(self):
		return copy.deepcopy(self)

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
	print(am.idx)
	print(am.uid)
	print(am.next)

	a = Linker((10,10))
	b = Linker((20,10))
	c = Linker((30,10))
	a + b + c
	print(hash(b), hash(a))

	ac = Container((10,10))
	bc = Container((20,10))
	cc = Container((30,10))
	dc = Container([ac, bc, cc, (20,30)])
	print(cc.next.next)
