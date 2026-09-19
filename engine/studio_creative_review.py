"""One media-review presentation for native and shared-project production.

This is a projection of existing production evidence, not another approval
ledger. Internal failures remain available to production support in the full
journey record; creatives keep their place in the media review flow.
"""
import re


def present(current, operation=None, busy=False):
    review=current.get('review') or {}
    phase=current['phase']
    operation=operation or {}
    waiting=operation.get('status')=='needs-decision' or phase=='dependency'
    see=review.get('seePackage')
    outcomes=review.get('outcomes') or {}
    see_current=bool(see.get('approved')) if see is not None else bool(review.get('seeCurrent') or (outcomes.get('see') or {}).get('status')=='approved')
    requires_audio=current.get('requiresAudio',True)
    audio_current=not requires_audio or bool(review.get('audioCurrent') or (outcomes.get('hear') or {}).get('status')=='approved')
    stage=('watch' if phase in ('film','complete') or (see_current and audio_current)
           else 'hear' if phase=='audio' or see_current else 'see')
    if waiting or busy:
        # Keep a backend failure in the stage whose operation was being prepared.
        # Do not turn a technical failure into a new image/audio approval request.
        step=operation.get('pending') or ''
        stage=('watch' if re.search(r'render|film|assemble',step)
               else 'hear' if re.search(r'audio|timing',step) else stage)
    media=review.get('videos') if stage=='watch' else [review.get('audio')] if stage=='hear' else review.get('images')
    has_media=any(isinstance(m,dict) and m.get('url') for m in (media or []))
    reviewable=(phase=='film' if stage=='watch' else phase=='audio' and not audio_current if stage=='hear' else phase=='images' and not see_current)
    state=('complete' if phase=='complete' else 'waiting' if waiting else 'preparing' if busy
           else 'review' if has_media and reviewable else 'ready')
    if state=='ready' and (current.get('disclosure') or {}).get('ready') is False:
        waiting=True
        state='waiting'
    noun={'see':'image','hear':'audio','watch':'video'}[stage]
    title={'review':f'Review your {noun}','ready':f'Create your {noun}',
           'preparing':f'Studio is preparing your {noun}',
           'waiting':'Waiting for Studio','complete':'Video approved'}[state]
    stopped=(operation.get('decision') or {}).get('issue') if waiting else None
    from studio_producer_language import stopped_message
    message=((stopped_message(stopped, stage=operation.get('pending')) if stopped else
              'Your approved work is saved. Studio needs one more step before it can continue.') if waiting else
             'Your approved work stays available while Studio prepares the next result.' if busy else
             'Approve this version or request another version.' if state=='review' else
             'Studio handles direction, references and preparation.' if state=='ready' else
             'The accepted video is saved in the scene.')
    if waiting and operation.get('intent')=='changes':
        title='Changes requested'
        message='Your feedback is saved with this version. Studio needs to prepare the revision before another video can be created.'
    producer=(operation.get('decision') or {}).get('producer') if waiting else None
    return {'stage':stage,'state':state,'title':title,'message':message,'producer':producer,
            'canApprove':state=='review' and (stage!='see' or see is None or bool(see.get('ready'))),'canRequestChanges':state=='review', 'canCreate':state=='ready' and not (stage=='see' and see and see.get('directorApproved') and not see.get('ready')),
            'approveLabel':f'Approve {noun}','createLabel':f'Create {noun}',
            'alternativeLabel':'Request another version',
            'stages':{'see':{'approved':see_current},'hear':{'approved':audio_current,'skipped':not requires_audio},
                      'watch':{'approved':phase=='complete'}},
            'supportRequired':waiting,'next':current.get('next')}
