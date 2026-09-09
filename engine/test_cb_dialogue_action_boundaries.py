"""Regression: soft line breaks after speech must not turn action into HEAR."""
import cb_intake

def test_unseparated_action_stays_out_of_dialogue():
    source = '''EXT. CLEARING — MORNING
KEEN
Uh-oh—
He rushes forward — grabs the prop.
KEEN
Ow!
It smacks his tail.
ZENNY
Calm down.
Above — a bee laughs.
KEEN
It almost worked.
Behind Keen — the machine collapses.
'''
    result = cb_intake.parse_script(source, log=lambda *args: None)
    assert [e['text'] for e in result['events'] if e['type'] == 'dialogue'] == [
        'Uh-oh—', 'Ow!', 'Calm down.', 'It almost worked.']
    actions = ' '.join(e['text'] for e in result['events'] if e['type'] == 'action')
    assert 'He rushes forward' in actions and 'It smacks his tail' in actions

def test_multiline_spoken_dialogue_is_preserved():
    result = cb_intake.parse_script('EXT. CLEARING — MORNING\nKEEN\nIt almost worked.\nI can try again.\n', log=lambda *args: None)
    assert [e['text'] for e in result['events'] if e['type'] == 'dialogue'] == ['It almost worked. I can try again.']
