import sys
import json
import base64
import hashlib
import unittest
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import track24

class TrackingTests(unittest.TestCase):
    def test_literal_escapes(self):
        self.assertEqual(track24.literal(r'var cp="\x61\x62";', 'cp'), 'ab')

    def test_endpoint(self):
        self.assertEqual(track24.discover_endpoint('var trackingUrl="/ajax/test.ajax.php";'),
                         'https://track24.ru/ajax/test.ajax.php')

    def test_packed_endpoint(self):
        # Synthetic packer fixture, not a captured user session.
        text = r'''eval(function(p,a,c,k,e,d){return p}('0 a=["\\x2f\\x61\\x6a\\x61\\x78\\x2f\\x74\\x2e\\x61\\x6a\\x61\\x78\\x2e\\x70\\x68\\x70"];0 b=a[1];',12,12,'var|||||||||||trackingUrl'.split('|')));'''
        self.assertEqual(track24.discover_endpoint(text), 'https://track24.ru/ajax/t.ajax.php')

    def test_external_endpoints_rejected(self):
        for value in ['https://example.com/ajax/a', '//evil.test/ajax/a', 'http://track24.ru/ajax/a']:
            with self.assertRaises(ValueError): track24.validate_endpoint(value)

    def test_decrypt_synthetic(self):
        salt, iv, password = b'12345678', b'0123456789abcdef', 'test-only'
        material, prev = b'', b''
        while len(material) < 48:
            prev = hashlib.md5(prev + password.encode() + salt).digest()
            material += prev
        expected = {'status': 'ok', 'data': {'trackCode': 'TEST00001'}}
        cipher = AES.new(material[:32], AES.MODE_CBC, iv).encrypt(pad(json.dumps(expected).encode(),16))
        envelope = {'ct': base64.b64encode(cipher).decode(), 'iv': iv.hex(), 's': salt.hex()}
        self.assertEqual(track24.decrypt(envelope,password), expected)

    def test_summary(self):
        result={'status':'ok','data':{'trackCode':'TEST00001','deliveredStatus':'0',
            'lastPoint':{'id':'test-event','operationDateTime':'01.01.2000 12:00:00'}}}
        self.assertFalse(track24.summary(result)['delivered'])
        self.assertIsNone(track24.summary(result)['timezone'])

if __name__ == '__main__': unittest.main()
