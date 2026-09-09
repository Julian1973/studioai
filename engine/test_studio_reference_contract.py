from studio_reference_contract import complete_identity_slots, required_cast, receipt

def test_missing_opening_cast_is_attached_without_mutating_source():
    shot={'charactersInFrame':['Keen','Fuzzby','Zenny']}
    slots={'@图1':'Keen','@图2':'scene plate'}
    result=complete_identity_slots(slots,required_cast(shot))
    assert list(result.values())==['Keen','scene plate','Fuzzby','Zenny']
    assert len(slots)==2
    assert complete_identity_slots(result,required_cast(shot))==result

def test_later_entry_is_not_added_to_opening():
    assert required_cast({'openingCharactersInFrame':['Keen'],'charactersInFrame':['Keen','Fuzzby']})==['Keen']
    assert required_cast({'openingCharactersInFrame':[],'charactersInFrame':['Keen']})==[]

def test_receipt_does_not_claim_visual_approval():
    assert receipt([{'role':'prop continuity','path':'a.png'}])['visualFidelity']=='requires-human-review'
