from tools.audit_studio_sources import audit


def test_active_source_references_and_documentation_are_resolvable():
    result = audit()
    assert result['pythonFilesParsed'] > 100
    assert result['runtimeSkills']
    assert result['ready'], result['issues']


def test_audit_reports_missing_import_worker_and_document_link(tmp_path):
    for name in ('engine','tools','cb-studio','skills','docs'):
        (tmp_path/name).mkdir()
    (tmp_path/'engine/worker.py').write_text('import cb_missing\nworker = "cb_retired.py"\n')
    (tmp_path/'README.md').write_text('[instructions](missing.md)\n')
    result = audit(tmp_path)
    assert not result['ready']
    assert {item['kind'] for item in result['issues']} == {'missing-local-import','missing-worker','broken-doc-link'}
