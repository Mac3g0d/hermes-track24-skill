#!/usr/bin/env python3
"""Read public Track24 tracking data; never replay another session's credentials."""
import argparse
import base64
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

ORIGIN = 'https://track24.ru'


def js_string(value):
    # Deliberately support only the escapes seen in Track24 literals.
    value = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m[1], 16)), value)
    value = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), value)
    return value.replace(r'\/', '/').replace(r'\"', '"').replace(r"\'", "'")


def literal(text, name):
    match = re.search(r'\b' + re.escape(name) + r'\s*=\s*([\x27\x22])((?:\\.|(?!\1).)*)\1', text)
    if not match:
        raise ValueError('Missing page literal: ' + name)
    return js_string(match[2])


def discover_endpoint(html):
    try:
        value = literal(html, 'trackingUrl')
    except ValueError:
        value = None
        # Decode the observed dictionary-packed assignment as DATA, never eval JS.
        pattern = r"\}\('((?:\\.|[^'\\])*)',(\d+),(\d+),'([^']*)'\.split\('\|'\)"
        for match in re.finditer(pattern, html):
            packed, radix, count, words = match.groups()
            radix, count = int(radix), int(count)
            if not 2 <= radix <= 36 or count > 5000 or len(packed) > 100000:
                continue
            words = words.split('|')
            digits = '0123456789abcdefghijklmnopqrstuvwxyz'
            def number(n):
                result = ''
                while n:
                    n, r = divmod(n, radix)
                    result = digits[r] + result
                return result or '0'
            for n in range(min(count, len(words)) - 1, -1, -1):
                if words[n]:
                    packed = re.sub(r'\b' + number(n) + r'\b', lambda _: words[n], packed)
            if 'trackingUrl' not in packed:
                continue
            # Remove the outer packer's JS-string escaping once.
            packed = packed.replace('\\\\', '\\')
            strings = re.findall(r'"((?:\\.|[^"\\])*)"', packed)
            for candidate in strings:
                candidate = js_string(candidate)
                if candidate.startswith('/ajax/') and candidate.endswith('.ajax.php'):
                    value = candidate
                    break
            if value:
                break
        if not value:
            raise ValueError('Cannot discover tracking endpoint; supply --endpoint from DevTools')
    return validate_endpoint(value)


def validate_endpoint(value):
    url = urllib.parse.urljoin(ORIGIN + '/', value)
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != 'https' or parts.netloc != 'track24.ru'
            or not parts.path.startswith('/ajax/') or parts.query or parts.fragment):
        raise ValueError('Endpoint must be an HTTPS /ajax/ URL on track24.ru')
    return url


def decrypt(envelope, password):
    if 'ct' not in envelope:
        return envelope
    salt = bytes.fromhex(envelope['s'])
    iv = bytes.fromhex(envelope['iv'])
    if len(salt) != 8 or len(iv) != 16:
        raise ValueError('Unexpected CryptoJS salt/IV length')
    material, previous = b'', b''
    while len(material) < 48:
        previous = hashlib.md5(previous + password.encode('utf-8') + salt).digest()
        material += previous
    ciphertext = base64.b64decode(envelope['ct'], validate=True)
    plain = AES.new(material[:32], AES.MODE_CBC, iv).decrypt(ciphertext)
    return json.loads(unpad(plain, 16).decode('utf-8'))


def fetch(url, timeout, data=None):
    headers = {'Accept': 'application/json, text/javascript, */*; q=0.01'}
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read(8_000_001)
        if len(body) > 8_000_000:
            raise ValueError('Response exceeds size limit')
        return body


def track(code, endpoint=None, timeout=25):
    # Preserve the exact identifier; reject rather than repair invalid input.
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.()/\-]{4,31}', code):
        raise ValueError('Invalid tracking identifier; input was not normalized')
    html = fetch(ORIGIN + '/?' + urllib.parse.urlencode({'code': code}), timeout).decode('utf-8')
    password = literal(html, 'cp')
    endpoint = validate_endpoint(endpoint) if endpoint else discover_endpoint(html)
    form = urllib.parse.urlencode({'code': code, 'selectedService': '', 'lng': 'ru',
                                  'sort': 'true', 'grouped': 'false', 'type': 'cache'}).encode()
    envelope = json.loads(fetch(endpoint, timeout, form))
    result = decrypt(envelope, password)
    if result.get('challenge'):
        raise ValueError('Site challenge requires operator action; not bypassed')
    if result.get('status') != 'ok':
        raise ValueError('Tracking service returned a non-ok status')
    data = result.get('data')
    if not isinstance(data, dict) or data.get('trackCode') != code:
        raise ValueError('Response does not match the exact requested identifier')
    return result


def summary(result):
    data = result['data']
    point = data.get('lastPoint') or {}
    return {'track': data['trackCode'], 'status': result['status'],
            'last_event_id': point.get('id'),
            'operation_time': point.get('operationDateTime'),
            'operation': point.get('operationAttribute'),
            'carrier': point.get('serviceName'),
            'delivered': str(data.get('deliveredStatus')) == '1',
            'source_updated_at': data.get('trackUpdateDateTime'),
            'sources': result.get('sources'), 'timezone': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('code')
    parser.add_argument('--endpoint', help='Optional observed Track24 /ajax/ URL')
    parser.add_argument('--timeout', type=float, default=25)
    args = parser.parse_args()
    if not 0 < args.timeout <= 120:
        parser.error('--timeout must be between 0 and 120 seconds')
    try:
        print(json.dumps(summary(track(args.code, args.endpoint, args.timeout)), ensure_ascii=False))
    except urllib.error.HTTPError as exc:
        print(json.dumps({'ok': False, 'error': 'http_error', 'http_status': exc.code}), file=sys.stderr)
        return 1
    except Exception as exc:
        # No raw response, keys, cookies, UUIDs or addresses in diagnostics.
        print(json.dumps({'ok': False, 'error': type(exc).__name__}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
