from test_studio_production import setup, command
from studio_episode_covers import covers, first_shot


def test_episode_cover_is_its_own_first_keyframe(setup):
    p,ws,t,_=setup
    command(p,'budget',amountUsd=5)
    image=p.snapshot('first','1')['state']['shots'][0]['outcomes']['see']['files'][0]['path']
    assert covers(ws,'first',lambda *a: {})['covers']['1']['url']=='/'+image
    assert covers(ws,'second',lambda *a: {})['covers']['1']['url'] is None


def test_split_first_shot_and_no_later_shot_fallback():
    assert first_shot([{'shotId':'S1.SH2'},{'shotId':'S1.SH1A'}])['shotId']=='S1.SH1A'
    assert first_shot([{'shotId':'S1.SH2'},{'shotId':'S2.SH1'}]) is None
