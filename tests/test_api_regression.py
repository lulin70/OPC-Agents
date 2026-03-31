#!/usr/bin/env python3
import requests

base = 'http://localhost:5009'
results = []

def check(name, url, fn):
    try:
        r = requests.get(url, timeout=5)
        ok = fn(r)
        results.append((name, ok, ''))
    except Exception as e:
        results.append((name, False, str(e)))

def test_api_regression():
    check('Health', f'{base}/api/health/', lambda r: r.status_code == 200)
    check('Tasks', f'{base}/api/tasks', lambda r: r.status_code == 200)
    check('Finance', f'{base}/finance', lambda r: r.status_code == 200)
    check('Monitoring', f'{base}/monitoring', lambda r: r.status_code == 200)
    check('Departments', f'{base}/api/departments', lambda r: r.status_code == 200)
    check('Agents', f'{base}/api/agents/', lambda r: r.status_code == 200)

    passed = sum(1 for _, ok, _ in results)
    for name, ok, err in results:
        s = 'PASS' if ok else 'FAIL'
        e = f' ({err})' if err else ''
        print(f'  {s} {name}{e}')
    print(f'\nResult: {passed}/{len(results)} passed')
    assert passed == len(results), f'{len(results)-passed} tests failed'
