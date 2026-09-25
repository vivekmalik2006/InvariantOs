import sys
sys.path.insert(0, '.')
from orchestrator.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Health check
r = client.get('/api/health')
assert r.status_code == 200 and r.json()['status'] == 'ok', f'Health failed: {r.text}'
print('GET /api/health OK')

# Get rules
r = client.get('/api/rules')
assert r.status_code == 200
data = r.json()
rule_count = len(data['rules'])
assert rule_count == 8, f'Expected 8 rules, got {rule_count}'
rule_ids = [rule['id'] for rule in data['rules']]
assert 'RULE-001' in rule_ids, 'RULE-001 not in rules'
print(f'GET /api/rules OK — {rule_count} rules loaded, RULE-001 present')

# Empty diff: Pydantic min_length=1 returns 422 (validation error) before route handler
r = client.post('/api/analyze', json={'diff': ''})
assert r.status_code == 422, f'Expected 422 for empty diff, got {r.status_code}'
print('POST /api/analyze (empty diff) -> 422 (Pydantic validation) OK')

# Whitespace-only diff: passes Pydantic but route handler returns 400
r = client.post('/api/analyze', json={'diff': '   '})
assert r.status_code == 400, f'Expected 400 for whitespace diff, got {r.status_code}'
print('POST /api/analyze (whitespace diff) -> 400 OK')

# Missing report should return 404
r = client.get('/api/report/nonexistent-id')
assert r.status_code == 404, f'Expected 404, got {r.status_code}'
print('GET /api/report/nonexistent-id -> 404 OK')

print()
print('ALL API ENDPOINT TESTS PASSED')
