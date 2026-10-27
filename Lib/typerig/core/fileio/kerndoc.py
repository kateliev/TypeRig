# MODULE: TypeRig / IO / Kerning documents (tr-kern)
# -----------------------------------------------------------
# A font for TR Kern outside an editor: a .trfont, a UFO or a designspace,
# read into a core Font with what kerning work needs, and saved back
# without touching anything else.
#
#   .trfont      read and written in full (TrFontIO): it is TypeRig's own format
#   .ufo         a light Font: glyph names, unicodes, components (default layer),
#                groups, kerning, the TR Kern lib key; one master
#   .designspace the same for every source: one master per source with its
#                location and its own kerning; groups, glyphs and the lib key
#                from the default source
# Saving a UFO / designspace writes only kerning.plist and groups.plist of
# every source UFO (and the TR Kern key of the default source's lib.plist):
# outlines, info and features are never rewritten.
#
#   doc = KernDocument.load(path); doc.font (core Font); doc.save()
#   doc.host() -> core actions/kern_font.CoreFontKernHost with components
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function

import os
import plistlib

from typerig.core.objects.font import Font
from typerig.core.objects.glyph import Glyph
from typerig.core.objects.master import Master, Masters
from typerig.core.objects.axis import Axis
from typerig.core.objects.groups import Groups
from typerig.core.objects.kern import Kerning

__version__ = '0.1.0'

LIB_KEY = 'com.typerig.kern'		# kern_actions.LIB_KEY (kept here to avoid an actions import)
KINDS = ('trfont', 'ufo', 'designspace')


def kind_of(path):
	ext = os.path.splitext(str(path).rstrip(os.sep))[1].lower().lstrip('.')
	return ext if ext in KINDS else None


# - plist helpers ----------------------------------------------------------------
def _read(path, default):
	if not os.path.exists(path):
		return default
	with open(path, 'rb') as f:
		return plistlib.load(f)


def _write(path, data):
	'''Write a plist; an empty one removes the file (UFO: optional files).'''
	if not data:
		if os.path.exists(path):
			os.remove(path)
		return
	with open(path, 'wb') as f:
		plistlib.dump(data, f, sort_keys=True)


def _glyph_dir(ufo):
	layers = _read(os.path.join(ufo, 'layercontents.plist'), [['public.default', 'glyphs']])
	return os.path.join(ufo, dict((n, d) for n, d in layers).get('public.default', 'glyphs'))


def _glyphs(ufo):
	'''[(name, unicodes, component names)] of the default layer.'''
	from fontTools.ufoLib.glifLib import GlyphSet
	gs = GlyphSet(_glyph_dir(ufo), validateRead=False)
	unicodes = gs.getUnicodes()
	components = gs.getComponentReferences()		# {glyph: [bases]}
	order = _read(os.path.join(ufo, 'lib.plist'), {}).get('public.glyphOrder') or []
	names = [n for n in order if n in gs] + sorted(n for n in gs.keys() if n not in set(order))
	return [(n, list(unicodes.get(n) or []), list(components.get(n) or [])) for n in names]


def _kerning(ufo):
	flat = {}
	for first, rights in _read(os.path.join(ufo, 'kerning.plist'), {}).items():
		for second, value in rights.items():
			flat[(first, second)] = value
	return Kerning.from_pairs(flat)


def _nested(kerning):
	out = {}
	for p in (kerning.data if kerning is not None else []):
		out.setdefault(p.first, {})[p.second] = int(p.value)
	return out


# - Document -------------------------------------------------------------------
class KernDocument(object):
	'''A font file for TR Kern: font (core Font), kind, path, sources {master: ufo path}.'''

	def __init__(self, font, path, kind, sources=None, components=None):
		self.font = font
		self.path = path
		self.kind = kind
		self.sources = sources or {}
		self.components = components or {}

	@classmethod
	def load(cls, path):
		path = str(path).rstrip(os.sep)
		kind = kind_of(path)
		if kind == 'trfont':
			from typerig.core.fileio.trfont import TrFontIO
			return cls(TrFontIO.read(path), path, kind)
		if kind == 'ufo':
			return cls._load_sources(path, kind, [(None, path, {}, True)], [])
		if kind == 'designspace':
			from fontTools.designspaceLib import DesignSpaceDocument
			ds = DesignSpaceDocument.fromfile(path)
			default = ds.findDefault()
			base = os.path.dirname(os.path.abspath(path))
			sources = []
			for sd in ds.sources:
				ufo = sd.path or os.path.join(base, sd.filename)
				name = sd.name or sd.styleName or os.path.splitext(os.path.basename(ufo))[0]
				sources.append((name, ufo, dict(sd.location or {}), sd is default))
			if not any(s[3] for s in sources) and sources:
				sources[0] = sources[0][:3] + (True,)
			axes = [Axis(a.name, a.tag, a.minimum, a.default, a.maximum) for a in ds.axes]
			return cls._load_sources(path, kind, sources, axes)
		raise ValueError('Not a .trfont, .ufo or .designspace: %s' % path)

	@classmethod
	def _load_sources(cls, path, kind, sources, axes):
		default_ufo = next(ufo for _n, ufo, _l, d in sources if d)
		info = _read(os.path.join(default_ufo, 'fontinfo.plist'), {})
		glyphs, components = [], {}
		for name, unicodes, comps in _glyphs(default_ufo):
			glyphs.append(Glyph(name=name, unicodes=unicodes))
			if comps:
				components[name] = comps
		masters, source_paths, master_kerning = [], {}, {}
		for name, ufo, location, is_default in sources:
			name = name or str(_read(os.path.join(ufo, 'fontinfo.plist'), {}).get('styleName') or 'Default')
			masters.append(Master(name, name, location, is_default=is_default))
			source_paths[name] = ufo
			if not is_default:
				master_kerning[name] = _kerning(ufo)
		groups = Groups()
		for gname, members in _read(os.path.join(default_ufo, 'groups.plist'), {}).items():
			groups.set(gname, list(members))
		lib = {}
		stored = _read(os.path.join(default_ufo, 'lib.plist'), {}).get(LIB_KEY)
		if stored:
			lib[LIB_KEY] = stored
		from typerig.core.objects.font import FontInfo
		font = Font(glyphs, info=FontInfo(str(info.get('familyName') or os.path.splitext(os.path.basename(path))[0]),
		                                  str(info.get('styleName') or '')),
		            axes=axes, masters=Masters(masters), groups=groups, kerning=_kerning(default_ufo),
		            master_kerning=master_kerning, lib=lib)
		return cls(font, path, kind, source_paths, components)

	def save(self):
		'''Write the kerning back (UFO / designspace: kerning.plist, groups.plist, TR Kern lib key only).'''
		if self.kind == 'trfont':
			from typerig.core.fileio.trfont import TrFontIO
			TrFontIO.write(self.font, self.path)
			return [self.path]
		written = []
		groups = {g.name: list(g.members) for g in self.font.groups.data}
		default = self.font.default_master_name()
		for master, ufo in self.sources.items():
			_write(os.path.join(ufo, 'kerning.plist'), _nested(self.font.kerning_for(master)))
			_write(os.path.join(ufo, 'groups.plist'), groups)
			if master == default:
				lib_path = os.path.join(ufo, 'lib.plist')
				lib = _read(lib_path, {})
				if self.font.lib.get(LIB_KEY):
					lib[LIB_KEY] = self.font.lib[LIB_KEY]
				else:
					lib.pop(LIB_KEY, None)
				_write(lib_path, lib)
			written.append(ufo)
		return written

	def host(self):
		'''A TR Kern host on this document (components from the UFO when read from one).'''
		from typerig.core.actions.kern_font import CoreFontKernHost
		doc = self

		class _Host(CoreFontKernHost):
			def components(self):
				return dict(doc.components) if doc.components else CoreFontKernHost.components(self)

		return _Host(self.font, self.path)
