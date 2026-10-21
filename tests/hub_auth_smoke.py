"""Non-mutating auth checks: HUB_TEST_URL, HUB_TEST_USER, HUB_TEST_PASSWORD.
Optional HUB_TEST_WORKER_TOKEN checks the narrow machine-endpoint exception.
"""
import os
import requests

base = os.environ['HUB_TEST_URL'].rstrip('/')
s = requests.Session()
for path in ['/', '/easyrea', '/reports', '/api/worker/health', '/api/reports', '/feeds/google/BG-comparison.json']:
    r = s.get(base + path, allow_redirects=False, timeout=30)
    assert r.status_code == (401 if path.startswith('/api/') else 307), (path, r.status_code)
r = s.post(base + '/api/auth/login', data={'username': 'homesector', 'password': 'wrong'}, headers={'Origin': base}, allow_redirects=False, timeout=30)
assert r.status_code == 303 and 'error=credentials' in r.headers['Location']
r = s.post(base + '/api/auth/login', data={'username': os.environ['HUB_TEST_USER'], 'password': os.environ['HUB_TEST_PASSWORD'], 'next': '/easyrea'}, headers={'Origin': base}, allow_redirects=False, timeout=30)
assert r.status_code == 303 and r.headers['Location'].endswith('/easyrea'), r.status_code
cookie = r.headers['Set-Cookie']
assert all(t in cookie for t in ['HttpOnly', 'Secure', 'SameSite=strict'])
token = cookie.split(';')[0]
headers = {'Cookie': token}
r = s.get(base + '/easyrea', headers=headers, timeout=30)
assert r.status_code == 200 and 'Изход' in r.text
# New sessions prevent the successful cookie from masking rejection tests.
assert requests.get(base + '/api/worker/health', headers={'Cookie': token[:len(token)//2] + ('a' if token[len(token)//2] != 'a' else 'b') + token[len(token)//2+1:]}, timeout=30).status_code == 401
assert s.post(base + '/api/collector', headers={**headers, 'Origin': 'https://attacker.example'}, timeout=30).status_code == 403
worker = os.environ.get('HUB_TEST_WORKER_TOKEN', 'invalid-worker-key')
assert requests.get(base + '/api/worker/health', headers={'Authorization': 'Bearer ' + worker}, timeout=30).status_code == 401
if os.environ.get('HUB_TEST_WORKER_TOKEN'):
    assert requests.get(base + '/api/catalog-cache', headers={'Authorization': 'Bearer ' + worker}, timeout=30).status_code != 401
r = s.post(base + '/api/auth/logout', headers={**headers, 'Origin': base}, allow_redirects=False, timeout=30)
assert r.status_code == 303 and 'Max-Age=0' in r.headers['Set-Cookie']
s.cookies.clear()
assert s.get(base + '/api/worker/health', timeout=30).status_code == 401
print('PASS: page/API/report protection, login, bad password, secure cookie, tamper rejection, CSRF, scoped worker key, logout')
