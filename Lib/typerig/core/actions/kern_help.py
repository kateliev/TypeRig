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

__version__ = '0.9.1'

HELP_TEXT = '''TR KERN — HELP

TR Kern manages the kerning of a font. This version has these tools:
- Pairs shows every pair of every master. You find, edit, change in bulk, copy between masters and lock pairs.
- Groups edits the kerning groups and their leaders. Optionally, it keeps the spacing as it is.
- Cleanup finds kerning that you can remove or simplify, and fixes it.
- Analyze shows problems in the kerning. It does not change the font.
- Rules copies kerning by analogy, for example from O V to Odieresis V. You keep the rules in the font.
- Strings makes proof strings and pair lists.
- Import puts kerning from an external source (an autokerner, DTL KernMaster) into your font. Your kerning groups do not change.
- Job composes the pairs for DTL KernMaster and writes its files: the pairs (KRN) and the classes (CLA).

Most buttons show an icon. Hold the pointer on a button to see its name and what it does.


TERMS

Pair — two sides with a kerning value. A side is a glyph or a group.
Group — a kerning group (class). A group is on the left side or on the right side of a pair.
Exception — a pair where at least one side is a glyph, not a group. It changes the value for that glyph only.
Class value — the value of a group pair, for example @T @o = -50.
Key glyph (leader) — the glyph that stands for a group. It is the leader that you set, else the member with the same name as the group, else the first member.
Source — kerning from outside the font: an AFM file, a KRN file with values, a compiled font (OTF or TTF), or a UFO.
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
- @O|@A — a group pair. Use * for any side and /regex/ for a pattern, for example /\\.sc$/|*.
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

At cursor — put the text cursor of the edit tab between two glyphs. Then click At cursor. The grid shows every pair that changes these two glyphs, and the box explains the value.

Keys — click a row in the grid first. Then:
- + or − adds or subtracts 5 units. With Shift: 1 unit. With Option: 25 units. The "In:" menu selects the masters.
- L locks the selected pairs, or unlocks them if all are locked.
- Space opens the selected pairs in a new edit tab (with the pattern of the Strings tab).
- Return edits the value of the selected row.

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


3. GROUPS

Select the side at the top left:
- Left side (1st): the group of a glyph when it is on the left of a pair. In Glyphs, this is the right group of the glyph.
- Right side (2nd): the group when the glyph is on the right of a pair. In Glyphs, this is the left group.
A glyph is in one group for each side. When you put a glyph in a group, it leaves its old group.

The list shows each group with its number of glyphs, the number of pairs that use it (all masters) and its leader. Select a group to see its glyphs on the right. The leader has a star (★).

Preserve rendering (on by default) — after each group change, the tool adds exceptions so that each glyph pair keeps the value that it had. The structure changes, the spacing does not. Turn it off if the glyphs must take the values of their new group.

Group changes are pending, like the changes of the Pairs tab. Click Apply (here or in the Pairs tab) to write them. Restore last undoes them.

To make a group: type a name under the list, select glyphs in Glyphs, then click +.
To rename a group: double-click its name and type the new name. The pairs of the group get the new name in all masters.
To delete groups: select them and click −. With Preserve rendering, their glyphs keep their values as exceptions.
To merge groups: select two or more and click Merge. They go into the first group.
Glyphs of a group (right side):
- Make leader — the selected glyph becomes the leader.
- Out of group — the selected glyphs leave the group.
- Add selected — the glyphs that you select in Glyphs join the group.
- Move to… — the selected glyphs go to another group.

Leaders — the leader stands for its group. DTL KernMaster kerns a class with its first glyph, so the CLA file of the Job tab puts the leader first. The import, Explain, Rules and the proof strings use the same leader. A leader change does not change the kerning, and it is saved in the font at once.
To copy the leaders from a CLA file (for example a file that KernMaster used), click the file button. The first glyph of each class becomes the leader of the group with the same name (_1 = left side, _2 = right side, no suffix = both sides).

Auto — makes groups from composites and suffixes. A glyph with one letter component joins the group of that letter (Aacute joins A). A glyph with a suffix joins the group of its base (a.ss01 joins a). A chain goes to its first base (Aogonek.ss01 joins A). Glyphs that have a group keep it. A glyph with two letter components (for example fi) does not join a group; the report shows it. If the base has no group, the tool makes a group with the name of the base. The changes are pending.

Validate — finds glyphs in two groups of one side, empty groups, glyphs that are not in the font, groups with the name of a glyph that is not a member, and pairs with a missing group or glyph.


4. CLEANUP

Each check finds first. Nothing changes until you click "Plan fixes" and then Apply. The checks use the kerning with the pending changes.

The checks:
- Pairs that change nothing — a pair that gives its glyph pairs the same values that they get without it. All pair kinds are checked. Fix: remove (the spacing does not change).
- Compress group pairs — the pairs of a group pair (for example @T @o and its exceptions) are written again with fewer pairs. Each glyph pair keeps its value. This finds glyph pairs that fit a class, and class values that the exceptions do not agree with. Regions with a locked pair are skipped.
- Pairs missing in some masters — "covered": another pair gives these glyphs a value in that master; "uncovered": they get 0.
  Missing fix: Fill resolved (default) writes the value that the master shows now, so nothing changes visually. If the glyph pairs of the missing pair have different values, the report says "approximate".
  Copy from master: the value of the master that you select.
  Copy nearest master: the value of the nearest master that has the pair (by the axis values of the masters).
  Interpolate (location): the value between the masters that have the pair, along the axis on which the masters differ. Outside these masters, or when more than one axis differs, the tool uses the nearest master and the report says so.
  Remove everywhere: the pair is removed from all masters.
- Pairs with a missing group or glyph — Fix: remove.
- Small values — values below "Small below". Fix: remove. This changes the spacing, so it is off by default.
- Sign flips and large spreads — a pair that is positive in one master and negative in another, or that changes by more than "Spread over" between masters. Report only.

Tolerance — "Pairs that change nothing" and "Compress" can move a glyph pair by this value (units). 0 keeps the spacing exactly.

To clean up:
1. Select the checks. Set the options.
2. Click Find. Read the report.
3. Click "Plan fixes". Then click Apply.


5. ANALYZE

Analyze shows problems in the kerning. It does not change the font, and it does not add pending changes. The analyses use the kerning with the pending changes. "Masters" selects one master or all masters.

The report is a tree: one branch for each analysis, then sections, then the findings. Orange — a finding; green — the tool looked and found nothing; normal — numbers only. Click a triangle to open or close a branch. Option-click opens all the branches under it. "Expand all" and "Collapse all" open or close the whole tree. "Copy report" copies the report as text.

The analyses:
- Health card — for each master: the number of pairs of each kind, the exceptions as a percentage of the group pairs, the group pairs as a percentage of all possible group pairs ("fill"), the smallest, middle and largest value, and the number of pairs with the value 0.
- Value histogram — how many values are in each range of "Bin" units. The report also shows:
  spikes: a range with "Spike ×" times more values than the ranges near it;
  values off the grid: the font uses steps of 10 or 5, but some values do not (often hand edits in autokerned kerning);
  extreme values: larger than "Extreme" (plus or minus);
  shape: a master whose distribution is different from the other masters by more than "Shape %". This needs three masters or more. A master that only kerns tighter or looser has the same shape.
- Exception pressure — a group pair where many glyph pairs get their value from exceptions, not from the group pair. The report shows group pairs with "Pressure %" or more. It also shows glyphs that have exceptions against "Culprits" or more groups. Such a glyph is often in the wrong group.
- Shadowed and fragile pairs — a group pair (or glyph + group pair) that more specific pairs replace for all of its glyph pairs ("shadowed": it never applies), or for "Fragile %" of them or more ("fragile"). Cleanup > "Pairs that change nothing" removes the shadowed pairs.
- Member divergence — a group member whose kerning against the other side is, on average, "Divergence" units or more from the middle value of its group. The report shows the group that the member is closer to, if there is one. Groups with fewer than "Members" glyphs are not checked.

To analyse:
1. Select the analyses. Set the options.
2. Click Run. Read the report.
3. Select one or more findings. Click "Show in Pairs" (or double-click a finding) to see their pairs in the Pairs tab. Click "Show pair" to see them in the edit tab.


6. RULES

A rule copies the kerning of one pair to other pairs. Write one rule on each line:
  destination pairs = source pair [@adjust]
Examples:
  Ö|V Ä|V = O|V            Odieresis V and Adieresis V get the value of O V.
  Ö|V = O|V @*1.1          the value of O V, times 1.1.
  Y|A A|Y A|V = V|A @-5    the value of V A, minus 5.
  *.sc|*.sc = *|*          every kerned glyph pair a b gives a.sc b.sc (if the font has them).
A side is a character, /glyphname, a glyph name or @group. # starts a comment. The rule files of FL Copy Kerning open without changes.

The value of the source is the value that the font shows for the two glyphs. A @group stands for its key glyph. If the source has no kerning, the tool skips the rule and tells you.

Each rule set has two options:
- Class (on by default): the tool writes a destination glyph as its group, if it has one.
- Live: the set runs again after each change of the kerning (an edit, a bulk operation, an import). Use it for kerning that must follow its source, for example accents and small caps.

To use rules:
1. Click + to make a rule set, or open a .txt rule file.
2. Type the rules. Select the masters with "In:".
3. Click "Plan selected" or "Plan all". The changes are pending.
4. Open the Pairs tab and click Apply.
The report under the rules shows mistakes with their line numbers.


7. STRINGS

1. Select the pairs:
   - Selected pairs or Shown pairs of the Pairs tab. A group stands for its key glyph.
   - All pairs of the master.
   - A × B: each glyph of A with each glyph of B. Type names, characters, @group, @* (all groups of that side) or a set: *Uppercase, *Lowercase, *Smallcaps, *Figures, *Marks, *Alternates, *Ligatures, *Other. A suffix (for example .sc) is added to each glyph of that side.
2. Select the pattern. FL and FR are the fillers, A and B are the pair, | is a space and \n is a new line.
3. Select the fillers. Type text, characters or /glyphname. "auto" uses HOH for capitals and non for other glyphs.
4. Click "New tab", or copy the text: /names (for Glyphs and FontLab), plain text (other apps) or KPX lines.


8. IMPORT — QUICK START

1. Open the Import tab.
2. Click "Add…" and select one or more sources: AFM, KRN with values, OTF, TTF or UFO.
3. Make sure that each source has the correct master. The tool finds the master from the file name.
4. If the master is wrong, select the source. Then use the "Set master…" menu.
6. Set the options (section 9). The defaults are correct for a complete autokerner export.
7. Click Preview. Read the report.
8. Click Apply. The tool keeps a snapshot first.
9. Read the self check at the end of the report.


9. IMPORT — THE OPTIONS

Class value — how the tool selects the value of a group pair from the values of its glyphs:
- Key glyph (default): the value of the key glyphs. For @T @o, this is the value of T o. If the source does not have T o, the tool uses Mode for that group pair and tells you.
- Mode: the value that most glyph pairs have.
- Median: the middle value.

Example: the source has T o -50, T oacute -50, Tcaron o -50, Tcaron oacute -20.
Key glyph and Mode both give @T @o = -50. The tool adds one exception: Tcaron oacute -20.

Tolerance — glyph pairs that are this close to the class value do not get an exception. Use it for noisy sources, for example 2 or 5 units.

Sources in detail:
- AFM — the KPX pairs. The CharMetrics list gives the coverage.
- KRN — only lines with a value.
- OTF / TTF — the kern feature (GPOS), as the font applies it: exceptions before classes, lookups added together. A font without GPOS kerning gives its old kern table. A variable font gives its default instance. All glyphs of the font are the coverage.
- UFO (a folder) — its kerning, applied through its own groups. All glyphs of the UFO are the coverage.
The tool always makes flat glyph pairs from a source first. Then it writes them on your groups.

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


10. IMPORT — NAMES

AFM files from a compiled font often use production names, for example uni0414. The tool finds the font glyph:
1. the same name,
2. the production name of a glyph,
3. a uniXXXX or uXXXXX name, by its Unicode value.
Pairs with a glyph that the tool does not find are not imported. The report shows these glyphs.


11. IMPORT — THE REPORT

Preview shows the plan for each master:
- added, changed, unchanged and removed pairs,
- the pairs by kind: CC (group + group), CG, GC, GG (glyph + glyph),
- warnings, glyphs that are not in the font, glyphs outside the coverage.
Apply writes the plan. Then it reads the master again and does a self check. The self check compares each glyph pair with the source. "The master renders the source exactly" means that the import is correct. A locked pair can show as a difference.


12. SNAPSHOTS AND RESTORE

Before Apply writes (Pairs or Import), the tool saves a snapshot of each master that changes. The snapshot is in a folder next to the font file: <font file>.trkern.
"Restore last" writes back the kerning from before the last Apply.
If the font is not saved, there is no folder. Then "Restore last" works only until you close the window.


13. JOB — DTL KERNMASTER

The Job tab writes the files that DTL KernMaster needs: one KRN file (the pairs to kern) for each master and one CLA file (the classes). It works like the FontRig Kern Job Composer, and it opens and saves the same composition files (JSON).

Compositions — a job is a list of blocks. A block has items. Each item is on the left side (1ST), on the right side (2ND), or on both. A block gives each 1ST item with each 2ND item. The job is all the blocks together. A pair that is in two blocks is written one time.

Items — glyph names, characters, @group, @* (all groups of that side) or a set: *Uppercase, *Lowercase, *Smallcaps, *Figures, *Marks, *Alternates, *Ligatures, *Other. An item can have more than one name, separated by spaces. A group name from a CLA file (for example @T_1) is also correct.

To make a job:
1. Click + under the blocks to make a block. Double-click its name to change it.
2. Type an item in the "New item" field and press Return. Or copy a list and click Paste ("quoted","names", /slash/names, names, separated by commas, or one name on each line).
3. Set 1ST and 2ND for each item.
4. Select the masters. "Use groups" writes a glyph as its group, if it has one.
6. Click Preview. Read what the files will have: the pairs of each block, the total, the warnings, the classes and the pairs.
7. Click "Export job" and select a folder.
To use the pairs that each master has now, select "Font kerning" in the Pairs menu.

Class names have the side at the end: _1 is the left side, _2 is the right side. For example, @T_1 and @o_2.

Leaders — DTL KernMaster kerns a class with its first glyph, the leader. The CLA file puts the leader of each group first. The same leader is the key glyph of the import (section 9), of Explain and of the proof strings. You set the leaders in the Groups tab (section 3). If a group has no leader, it is the member with the same name as the group, else the first member.

DTL KernMaster gives back AFM files. Import them in the Import tab. Export job sets the "Strip" text of the import, so that the AFM files find their masters.


14. COMMAND LINE (tr-kern)

TR Kern also works without an editor, on UFO, designspace and .trfont files: the command tr-kern (or python -m typerig.core.actions.kern_cli). It uses the same engine as this window. For a UFO or a designspace it writes only the kerning, the groups and the TR Kern settings; it does not change outlines, font info or features. Each write keeps a snapshot next to the font; "tr-kern restore" brings it back.
Commands: info, import, cleanup, analyze, job, rules, pairs, groups, restore. Type "tr-kern COMMAND -h" for the options of a command. Changes are only planned until you add --apply (import writes unless you add --dry-run).
'''
