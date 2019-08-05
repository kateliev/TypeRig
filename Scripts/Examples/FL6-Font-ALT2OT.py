#FLM: Font: Generate OT Features from alternates
# VER: 1.9
#----------------------------------
# Foundry:  FontMaker
# Typeface: Bolyar Sans
# Date:     28.01.2019
#----------------------------------

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont
from typerig.string import figureNames

from collections import defaultdict

# - Init ------------------------------------------------
font = pFont()
alt_mark = '.'
liga_mark = '_'
ban_list = ['subs', 'sups', 'dnom', 'numr']


# - Feature templates ------------------------------------
fea_template =  'feature {tag} {{ # {com}\n{body}\n}} {tag};\n'
aalt_feature = '\tfeature {tag};'
sub_template = '\tsub {glyph} by {glyph}.{suffix};'
sub_from_template = '\tsub {glyph} from [{group}];'
liga_template = '\tsub {glyphs} by {ligature};'

# - Feature templates with languages-----------------------
fea_template_lang = '''
feature {tag} {{
# {com}
	lookup {tag}_all {{
{body}
	}} {tag}_all;

# Default
lookup {tag}_all;
	
script cyrl; # Cyrillic
lookup {tag}_all;

script latn; # Latin
lookup {tag}_all;

language AZE ; # Azeri
language TRK ; # Turkish
language MOL ; # Moldavian
language ROM ; # Romanian
language CAT ; # Catalan
language CRT ; # Crimean Tatar

}} {tag};

'''

sub_template_lang = '\t' + sub_template
sub_from_template_lang = '\t' + sub_from_template
liga_template_lang = '\t' + liga_template

# - Process --------------------------------------------
aalt_store = []

# -- Alternates ----------------------------------------
alt_names = [g.name.split(alt_mark) for g in font.alternates()]
alt_refs = [(name[-1], alt_mark.join(name[:-1])) for name in alt_names]
alt_leads = defaultdict(list)
alt_groups = defaultdict(list)

# --- Alt features dict
for tag, glyph in alt_refs:
	alt_groups[tag].append(glyph)

# --- Build ALT features for every suffix
for key, value in alt_groups.iteritems():
	subs = '\n'.join([sub_template_lang.format(glyph=name, suffix=key) for name in value])
	font.setFeature(key ,fea_template_lang.format(tag=key, com=key, body=subs))
	aalt_store.append(key)
	print 'ADD:\t OT Feature: %s.' %key
	
	if 'cv' in key: # Duplicate CV featrues as SS
		key_replace = key.replace('cv', 'ss')
		font.setFeature(key_replace ,fea_template_lang.format(tag=key_replace, com=key_replace, body=subs))
		aalt_store.append(key_replace)
		print 'ADD:\t OT Feature: %s.' %key_replace



# -- Salt feature --------------------------------------------
salt_fea = 'salt'
salt_subs_list = []

# --- Alt leaders dict for salt_from template_lang
for name_tuple in alt_names:
	alt_lead = name_tuple[0]
	alt_suff = name_tuple[1]

	if alt_lead not in figureNames and alt_suff not in ban_list:
		alt_leads[alt_lead].append(alt_mark.join(name_tuple))

# --- Build substitution list
for key, value in alt_leads.iteritems():
	salt_subs_list.append(sub_from_template_lang.format(glyph=key, group=' '.join(value)))
	
salt_subs = '\n'.join(salt_subs_list)
font.setFeature(salt_fea, fea_template_lang.format(tag=salt_fea, com=salt_fea, body=salt_subs))
aalt_store.append(salt_fea)
print 'ADD:\t OT Feature: %s.' %salt_fea


# -- Ligatures --------------------------------------------
calt_fea = 'calt'
liga_names = [(g.name.replace(liga_mark, ' '), g.name) for g in font.ligatures()]

calt_subs = '\n'.join([liga_template_lang.format(glyphs=parts, ligature=liga) for parts, liga in liga_names])
font.setFeature(calt_fea, fea_template_lang.format(tag=calt_fea, com=calt_fea, body=calt_subs))
aalt_store.append(calt_fea)
print 'ADD:\t OT Feature: %s.' %calt_fea

# -- Access all alternates --------------------------------
#! BUGGY FL6 behaviour adding aalt feature messes up features ?! Why!
#! what is not working is commented out

aalt_fea = 'aalt'
aalt_insert = '\n'.join([aalt_feature.format(tag=fea_tag) for fea_tag in aalt_store])
print fea_template.format(tag=aalt_fea, com=aalt_fea, body=aalt_insert) # just print and copy it in the features panel
#font.setFeature(aalt_fea, fea_template.format(tag=aalt_fea, com=aalt_fea, body=aalt_insert))
#print 'ADD:\t OT Feature: %s.' %aalt_fea


# - Finish --------------------------------------------
#font.update()
print 'DONE.'
