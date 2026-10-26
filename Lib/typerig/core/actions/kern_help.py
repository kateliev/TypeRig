# MODULE: TypeRig / Core / Actions / Kern Help
# -----------------------------------------------------------
# TR Kern — Help tab text, the same on every host (Glyphs, FontLab,
# FontRig). Plain text, Simplified Technical English (ASD-STE100 rules,
# pragmatic mode): procedures in the imperative, max 20 words;
# descriptions max 25 words; one term per item. Terms used: source,
# master, pair, group, exception, class value, key glyph, coverage,
# scope, lock, snapshot, job. Keep in step with the windows when
# buttons or options change. Buttons are named by their tooltips.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------

from __future__ import unicode_literals

__version__ = '0.2.0'

HELP_TEXT = '''TR KERN — HELP

TR Kern manages the kerning of a font. This version has three tools:
- Pairs shows every pair of every master. You find, edit, change in bulk, copy between masters and lock pairs.
- Import puts kerning from an external source (an autokerner, DTL KernMaster) into your font. Your kerning groups do not change.
- Job writes the files that DTL KernMaster needs: a pair list (KRN) and the classes (CLA).

Most buttons show an icon. Hold the pointer on a button to see its name and what it does.


TERMS

Pair — two sides with a kerning value. A side is a glyph or a group.
Group — a kerning group (class). A group is on the left side or on the right side of a pair.
Exception — a pair where at least one side is a glyph, not a group. It changes the value for that glyph only.
Class value — the value of a group pair, for example @T @o = -50.
Key glyph — the glyph that stands for a group. It is the member with the same name as the group, else the first member.
Source — a file with flat glyph pairs: an AFM file, or a KRN file with values.
Coverage — the glyphs that a source knows. In an AFM file, these are the glyphs in its CharMetrics list.
Snapshot — a copy of the kerning before a change, kept in a folder next to the font.
Pending — a change that is planned but not written to the font yet.
Lock — a mark on a pair. No operation and no import changes a locked pair.


1. HOW THE FONT FINDS A KERNING VALUE

For two glyphs, the font uses the first pair that it finds, in this order:
1. glyph + glyph (for example T odieresis)
2. glyph + group (T @o)
3. group + glyph (@T odieresis)
4. group + group (@T @o)
If no pair applies, the value is 0. TR Kern uses this order everywhere.


2. PAIRS

The grid has one row for each pair and one column for each master. An empty cell means that the master does not have the pair.
Row colours: orange — the row has pending changes; grey — locked; blue — an exception with a group; purple — glyph + glyph.

Nothing is written to the font until you click Apply. A pending value shows a dot (•). The counter under the operations shows how many changes are pending.

To edit a value:
1. Double-click the cell.
2. Type the new value and press Return. To remove the pair from that master, delete the value.

To find pairs, type in the search field and press Return:
- T|* — every pair with T on the left side. A glyph also finds its group, so T|* also shows @T pairs.
- @O|@A — a group pair. Use * for any side and /regex/ for a pattern, for example /\.sc$/|*.
- V — a glyph or group on either side.
- <-50, >=10, =0, !=0 — values. A row matches if one master matches.
- master:Bold <-50 — the values of Bold only. Use quotes for names with spaces: master:"Semi Bold".
- missing, missing:Bold — pairs that a master does not have.
- spread>20 — the values of the masters differ by more than 20.
- kind:GG,CC — pair kinds (CC group + group, CG group + glyph, GC glyph + group, GG glyph + glyph).
- in:@O — group O is on a side, or a glyph of group O is on a side.
- locked, unlocked.
A space means "and". A semicolon (;) means "or". Example: T|* <-80; @O|@A
The Kind menu and the Missing box write into the search field.

Explain — select a row. The box under the operations shows how the font finds the value in each master. A group stands for its key glyph. To explain any glyph pair, search ?A|V.

Bulk — changes the selected rows. If no row is selected, it changes every row in the grid.
1. Select the operation and type the value. "Replace value" uses the second field for the new value.
2. Select the masters (In:).
3. Click Plan.
Operations: Set to, Add, Add away from 0 (moves values away from zero), Scale %, Round to, Clamp to ±, Remove if |v| <, Remove, Replace value. Only "Set to" adds a pair to a master that does not have it.

Master to master — works on the selected rows, or on all pairs if no row is selected:
- Copy: To = From × k + c.
- Interpolate: To = From + (Mix − From) × t. t 0 gives From, t 1 gives Mix. A pair that a master does not have counts as 0.
- Fill missing only: the target keeps its pairs. Overwrite: the target gets every pair.
Both operations use the pending values.

Lock / Unlock — select rows, then click Lock or Unlock. The locks are kept in the font.

Apply writes the pending changes. The tool keeps a snapshot first. Discard removes the pending changes. Restore last writes back the kerning from before the last Apply (Pairs or Import).


3. IMPORT — QUICK START

1. Open the Import tab.
2. Click "Add sources" and select one or more AFM files.
3. Make sure that each source has the correct master. The tool finds the master from the file name.
4. If the master is wrong, select the source. Then use the "Set master…" menu.
5. Set the options (section 4). The defaults are correct for a complete autokerner export.
6. Click Preview. Read the report.
7. Click Apply. The tool keeps a snapshot first.
8. Read the self check at the end of the report.


4. IMPORT — THE OPTIONS

Class value — how the tool selects the value of a group pair from the values of its glyphs:
- Key glyph (default): the value of the key glyphs. For @T @o, this is the value of T o. If the source does not have T o, the tool uses Mode for that group pair and tells you.
- Mode: the value that most glyph pairs have.
- Median: the middle value.

Example: the source has T o -50, T oacute -50, Tcaron o -50, Tcaron oacute -20.
Key glyph and Mode both give @T @o = -50. The tool adds one exception: Tcaron oacute -20.

Tolerance — glyph pairs that are this close to the class value do not get an exception. Use it for noisy sources, for example 2 or 5 units.

Absent pairs — what a glyph pair means if it is not in the source:
- Absent = 0 (default): the glyph pair must not be kerned. Use this for a complete export. Autokerners do not write pairs with the value 0.
- No opinion: the source did not look at the pair. The glyph pair gets the class value. Use this for a partial source, for example a filtered file.

Example: @T has T and Tcaron, @o has o, oacute and odieresis. The source has only T o, T oacute and Tcaron o, all -50.
With Absent = 0, the class value is -50 and the other three glyph pairs get 0.
With No opinion, all six glyph pairs get -50.

The tool warns you when the source fills less than half of the group pairs that it touches. Then the source is probably partial. Select No opinion.

Coverage — the tool never sets a glyph to 0 if the source does not know the glyph. Example: o.ss01 is in @o, but the AFM does not have o.ss01. Then o.ss01 keeps the class value.

Write scope — what happens to the kerning that is in the master now:
- Merge + clear stale (default): the tool writes the import. It removes the old pairs between glyphs that the source knows. Pairs with glyphs that the source does not know stay.
- Replace master: the tool removes all old pairs of the master. Then it writes the import.
- Merge: the tool writes the import. It removes nothing.

Round to — rounds the values of the source before the import, for example to 5 units. 0 does not round.
Drop below — removes source pairs that are smaller than this value (after rounding). 0 keeps all pairs.
Clamp — limits the values of the source to plus or minus this value. 0 does not limit.

Groups never change. The tool uses the groups that are in the font.

Locked pairs — the tool never changes a locked pair. The report shows them. You lock pairs in the Pairs tab.


5. IMPORT — NAMES

AFM files from a compiled font often use production names, for example uni0414. The tool finds the font glyph:
1. the same name,
2. the production name of a glyph,
3. a uniXXXX or uXXXXX name, by its Unicode value.
Pairs with a glyph that the tool does not find are not imported. The report shows these glyphs.


6. IMPORT — THE REPORT

Preview shows the plan for each master:
- added, changed, unchanged and removed pairs,
- the pairs by kind: CC (group + group), CG, GC, GG (glyph + glyph),
- warnings, glyphs that are not in the font, glyphs outside the coverage.
Apply writes the plan. Then it reads the master again and does a self check. The self check compares each glyph pair with the source. "The master renders the source exactly" means that the import is correct. A locked pair can show as a difference.


7. SNAPSHOTS AND RESTORE

Before Apply writes (Pairs or Import), the tool saves a snapshot of each master that changes. The snapshot is in a folder next to the font file: <font file>.trkern.
"Restore last" writes back the kerning from before the last Apply.
If the font is not saved, there is no folder. Then "Restore last" works only until you close the window.


8. JOB — DTL KERNMASTER

1. Open the Job tab.
2. Select the pairs:
   - Font kerning: the pairs that each master has now.
   - A × B: the pairs from the A list and the B list.
3. For A × B, type glyph names or groups. Use @name for a group and @* for all groups of that side. "Use groups" changes each glyph to its group.
4. Select the masters.
5. Click "Export job" and select a folder.
The tool writes one KRN file for each master and one CLA file for the font.

Class names in the files have the side at the end: _1 is the left side, _2 is the right side. For example, @T_1 and @o_2.

DTL KernMaster gives back AFM files. Import them in the Import tab. The groups of the font stay the same.
'''
