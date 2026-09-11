import json
import pytest
from pydantic import BaseModel
import studio_final_direction as F
import cb_departments as D
from test_cb_departments import _voice_line, _locked

class Direction(BaseModel):
    shotId:str
    composition:str
    charactersInFrame:list[str]
    canonicalStyleVersion:str
    canonicalStyleParagraph:str

def test_final_revision_is_returned_with_receipt(monkeypatch):
    draft=Direction(shotId='S3.SH1',composition='cups in foreground',charactersInFrame=['Sunny'],canonicalStyleVersion='1',canonicalStyleParagraph='canon')
    def reviewer(system,user,schema,**kw):
        assert kw['model']=='gpt-6-astra';assert kw['reasoning_effort']=='high'
        assert json.loads(user)['currentProduction']['storyboard']=='Sunny sets table'
        return draft.model_copy(update={'composition':'Sunny paw touching cup on existing table'})
    monkeypatch.setattr(F.cb_llm,'structured',reviewer)
    final,receipt=F.finalize('cinematography',draft,{'storyboard':'Sunny sets table'})
    assert final.composition=='Sunny paw touching cup on existing table'
    assert receipt['changed'] and receipt['outputHash']!=receipt['inputHash']

def test_final_director_cannot_change_cast(monkeypatch):
    draft=Direction(shotId='X',composition='x',charactersInFrame=['Sunny'],canonicalStyleVersion='1',canonicalStyleParagraph='canon')
    monkeypatch.setattr(F.cb_llm,'structured',lambda *a,**k:draft.model_copy(update={'charactersInFrame':['Aida']}))
    with pytest.raises(ValueError,match='charactersInFrame'):F.finalize('cinematography',draft,{})

def test_voice_final_output_reaches_recipe_and_word_guard(monkeypatch):
    draft=D.VoiceDirection(shotId='X',sceneIntention='false confidence',lines=[_voice_line()])
    monkeypatch.setattr(F.cb_llm,'structured',lambda *a,**k:draft.model_copy(deep=True))
    final,_=F.finalize('voice',draft,{'lockedVoiceLines':_locked()})
    D.validate_voice_direction(final,_locked())
    assert final.lines[0].takeRecipes[0].performedText==final.lines[0].performedText
    final.lines[0].performedText='I changed the words.'
    with pytest.raises(RuntimeError):D.validate_voice_direction(final,_locked())
