PYTHONPATH=engine python3 - <<'PYTEST'
import socket,pytest
socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('No network permitted'))
raise SystemExit(pytest.main(['engine/test_dynamic_state.py','engine/test_director_next_pass.py','engine/test_prompt_director_native_audit.py','engine/test_prompt_director_route_audit.py','engine/test_studio_prompt_director.py','engine/test_studio_request_evidence.py','engine/test_studio_production.py','engine/test_watch_retake.py','-q','--tb=short']))
PYTEST
