# General SEE keyframe handoff

7 September 2026. General workflow improvement, not a request to revise an existing episode or generate a specific shot.

SEE retains the scene plate and current opening frame. Adjacent shots now have a paired review showing the preceding accepted ending beside the current opening, and a link from the preceding shot to the next SEE review. Missing or unapproved predecessor media is not promoted to an opening frame.

For newly planned cuts with shotTransition stateSourceShotId, the keyframe attachment plan includes the preceding accepted final frame under a separate state-reference role. It controls world/action/prop continuity, not camera composition. The scene plate no longer imposes its viewpoint on a declared cut. The reference is included in the normal input hash and request preparation; it is not appended to the animation's opening anchor. Animation uses the independently approved new keyframe.

The existing SEE candidate approval and spending mechanisms remain in place. This does not automatically convert an existing continuation into a reverse or revise an accepted shot. A reverse still needs authored camera direction, and generation quality remains subject to human visual review.

Verification includes attachment-role isolation, approved predecessor enforcement, changed-frame detection, provider prompt compilation, media-map separation, and live SEE navigation using existing Episode 2 media without changing any production decision. Source audit and JavaScript syntax pass. Test results are in the accompanying logs. No provider generation was submitted.

Final focused suite: 108 passed. The broader run completed with 1,092 passed, 4 skipped and one failure in the newly added media-map fixture: its temporary path was outside the registry URL root. That fixture was corrected to isolate the URL mapper; both parameter cases and the complete 108-test focused set then passed. Production URL allow-list behavior was not relaxed. Live service reports stale=false, running=0; browser shows accepted-frame status and no horizontal overflow.
