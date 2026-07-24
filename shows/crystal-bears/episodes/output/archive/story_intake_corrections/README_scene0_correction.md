# Scene-0 correction, 2026-07-19

`Ep1_scene0_storyboard.json` (archived alongside this file) was produced by a real, billed `cb_creative.py scene 0` run against a beat (`S00-B01-TITLE-INVITATION`) that was never a real story scene — it was the screenplay's own title page (series title, episode title, credits, production company, draft-date stamp), mis-tagged Scene 0 by a bug in `cb_intake.parse_script`'s default scene number before the parser fix (2026-07-19). The storyboard invents a full "governing audience experience" for this front matter and is not usable production evidence.

Kept here as historical record, never deleted. The corresponding beat has been removed from the live canonical package (`cb-output/Ep1_The_Adventure_Begins_beat_package.json`); the pre-correction copy of that package is archived in this same directory (`Ep1_The_Adventure_Begins_beat_package_PRE_SCENE0_FIX_*.json`).
