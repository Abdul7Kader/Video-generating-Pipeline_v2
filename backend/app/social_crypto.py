"""AES-256-GCM with record binding; key lives separately from PostgreSQL."""
import base64
import json
import os
from pathlib import Path
import secrets
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.social_config import SocialError


def load_key():
    try:
        path=Path(os.environ['SOCIAL_TOKEN_KEY_PATH'])
        if path.stat().st_size > 4096: raise ValueError('oversized key')
        value=json.loads(path.read_text(encoding='utf-8'))
        key=base64.b64decode(value['key'],validate=True)
        if len(key)!=32: raise ValueError('wrong key length')
        return key
    except (KeyError, OSError, ValueError, TypeError) as exc:
        raise SocialError('SOCIAL_KEY_UNAVAILABLE','Der getrennte Schlüssel für Plattformtokens fehlt oder ist ungültig.') from exc


def seal(key, binding, value):
    nonce=secrets.token_bytes(12)
    return b'\x01'+nonce+AESGCM(key).encrypt(nonce,json.dumps(value).encode('utf-8'),binding.encode('utf-8'))


def unseal(key, binding, encrypted):
    try:
        data=bytes(encrypted)
        if data[:1]!=b'\x01' or len(data)>131072: raise ValueError('invalid envelope')
        return json.loads(AESGCM(key).decrypt(data[1:13],data[13:],binding.encode('utf-8')))
    except (InvalidTag, ValueError, TypeError) as exc:
        raise SocialError('SOCIAL_TOKEN_INVALID','Gespeicherte Plattformtokens konnten nicht sicher gelesen werden. Schlüssel und Sicherung prüfen.') from exc


if __name__ == '__main__':
    import argparse
    from app.storage_settings import private_write
    parser=argparse.ArgumentParser(description='Create a private token key without printing it.')
    parser.add_argument('path',type=Path)
    args=parser.parse_args()
    if args.path.exists(): parser.error('Existing key will not be replaced')
    private_write(args.path, {'key':base64.b64encode(AESGCM.generate_key(bit_length=256)).decode()})
    print('Privater Tokenschlüssel erstellt; getrennt von Datenbank und Git sichern.')
