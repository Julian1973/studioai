"""Project data owns alias expansion. No inferred object/story rewrite."""
import pytest
import studio_prompt_aliases as aliases


def shot(name='original golden honeycomb'):
    return {'trackedProductionObjects':[{'id':'object-1','name':name}],
            'providerAliases':{'whole comb':'object-1'}}

@pytest.mark.parametrize('name',['original golden honeycomb','blue parcel','silver orb'])
def test_explicit_alias_uses_project_object(name):
    assert aliases.protect_object_aliases('Carry the whole comb.',shot(name)) == f'Carry the {name}.'


def test_missing_object_is_unresolved():
    with pytest.raises(ValueError,match='canonical object'):
        aliases.protect_object_aliases('Carry the comb.',{'providerAliases':{'comb':'missing'}})


def test_object_not_inferred_from_project_noun():
    text='A honeycomb is beside a hair comb.'
    assert aliases.protect_object_aliases(text,{}) == text


def test_audio_and_spoken_words_never_rewritten():
    text='[Action]\nCarry the whole comb.\n[Audio]\nSay whole comb exactly.\n[Action]\nSpoken action: {whole comb}\n'
    final=aliases.protect_object_aliases(text,shot())
    assert '[Audio]\nSay whole comb exactly.' in final
    assert '{whole comb}' in final
    assert 'Carry the original golden honeycomb.' in final


def test_lifecycle_only_emits_project_rules():
    s=shot('parcel');s['trackedProductionObjects'][0].update(stateIn='held by Ada',prohibitedSubstitutions=['replacement suitcase'])
    rules=aliases.object_lifecycle_prompt_rules(s)
    assert 'No substitution: replacement suitcase.' in rules['exclude']
    assert 'honeycomb' not in str(rules)
    assert 'unverified' in str(rules['acceptance'])


def test_legacy_entrypoint_delegates_to_shared_implementation():
    assert aliases.protect_honeycomb_aliases is aliases.protect_object_aliases
    assert aliases.honeycomb_lifecycle_prompt_rules is aliases.object_lifecycle_prompt_rules
