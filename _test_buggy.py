import urllib.request, json, sys

patch = open('demo-repo/seeded-diff.patch', encoding='utf-8').read()
payload = json.dumps({'diff': patch, 'branch': 'feature/cancel-status-bug'}).encode()
req = urllib.request.Request(
    'http://127.0.0.1:8000/api/analyze',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r = urllib.request.urlopen(req, timeout=90)
result = json.loads(r.read().decode())

print("=== BUGGY DIFF RESULT ===")
print("final_verdict      :", result['final_verdict'])
print("final_verdict_label:", result['final_verdict_label'])
print("impacted_rules     :", [x['rule_id'] for x in result['impacted_rules']])
print()
print("validation_results:")
for v in result['validation_results']:
    print(" ", v['rule_id'], "->", v['verdict'])
    print("   ", v['explanation'][:100])
print()
print("security_findings:")
for s in result['security_findings']:
    print(" ", s['rule_id'], "->", s['verdict'], "|", s['explanation'][:80])
print()
print("test_gaps:")
for t in result['test_gaps']:
    print(" ", t['rule_id'], "-> has_coverage=", t['has_coverage'], "| path=", t.get('generated_test_path'))
