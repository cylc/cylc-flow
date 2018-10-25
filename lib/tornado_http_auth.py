# Mostly everything in this module is inspired or outright copied from Twisted's cred.
# https://github.com/twisted/twisted/blob/trunk/src/twisted/cred/credentials.py

import os, re, sys
import time
import binascii
import base64
import hashlib

from tornado.auth import AuthError


if sys.version_info >= (3,):
    def int_to_bytes(i):
        return ('%d' % i).encode('ascii')
else:
    def int_to_bytes(i):
        return b'%d' % i


def hexdigest_bytes(data, algo=None):
    return binascii.hexlify(hashlib.md5(data).digest())


def hexdigest_str(data, algo=None):
    return hashlib.md5(data).hexdigest()


class DigestAuthMixin(object):
    DIGEST_PRIVATE_KEY = b'secret-random'
    DIGEST_CHALLENGE_TIMEOUT_SECONDS = 60

    class SendChallenge(Exception):
        pass

    re_auth_hdr_parts = re.compile(
        '([^= ]+)'    # The key
        '='           # Conventional key/value separator (literal)
        '(?:'         # Group together a couple options
        '"([^"]*)"'   # A quoted string of length 0 or more
        '|'           # The other option in the group is coming
        '([^,]+)'     # An unquoted string of length 1 or more, up to a comma
        ')'           # That non-matching group ends
        ',?')         # There might be a comma at the end (none on last pair)

    def get_authenticated_user(self, check_credentials_func, realm):
        try:
            return self.authenticate_user(check_credentials_func, realm)
        except self.SendChallenge:
            self.send_auth_challenge(realm, self.request.remote_ip, self.get_time())

    def authenticate_user(self, check_credentials_func, realm):
        auth_header = self.request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Digest '):
            raise self.SendChallenge()

        params = self.parse_auth_header(auth_header)

        try:
            self.verify_params(params)
            self.verify_opaque(params['opaque'], params['nonce'], self.request.remote_ip)
        except AuthError:
            raise self.SendChallenge()

        challenge = check_credentials_func(params['username'])
        if not challenge:
            raise self.SendChallenge()

        received_response = params['response']
        expected_response = self.calculate_expected_response(challenge, params)

        if expected_response and received_response:
            if expected_response == received_response:
                self._current_user = params['username']
                return True
            else:
                raise self.SendChallenge()
        return False

    def parse_auth_header(self, hdr):
        items = self.re_auth_hdr_parts.findall(hdr)
        params = {}
        for key, bare, quoted in items:
            params[key.strip()] = (quoted or bare).strip()

        return params

    def create_auth_challenge(self, realm, clientip, time):
        nonce = binascii.hexlify(os.urandom(12))
        opaque = self.create_opaque(nonce, clientip, time)
        realm = realm.replace('\\', '\\\\').replace('"', '\\"')

        hdr = 'Digest algorithm="MD5", realm="%s", qop="auth", nonce="%s", opaque="%s"'
        return hdr % (realm, nonce.decode('ascii'), opaque.decode('ascii'))

    def send_auth_challenge(self, realm, remote_ip, time):
        self.set_status(401)
        self.set_header('www-authenticate', self.create_auth_challenge(realm, remote_ip, time))
        self.finish()
        return False

    def create_opaque(self, nonce, clientip, now):
        key = (nonce, clientip.encode('ascii'), int_to_bytes(now))
        key = b','.join(key)

        ekey = base64.b64encode(key).replace(b'\n', b'')
        digest = hexdigest_bytes(key + self.DIGEST_PRIVATE_KEY)
        return b'-'.join((digest, ekey))

    def get_time(self):
        return time.time()

    def verify_params(self, params):
        if not params.get('username'):
            raise AuthError('Invalid response, no username given')

        if 'opaque' not in params:
            raise AuthError('Invalid response, no opaque given')

        if 'nonce' not in params:
            raise AuthError('Invalid response, no nonce given')

    def verify_opaque(self, opaque, nonce, clientip):
        try:
            received_digest, received_ekey = opaque.split('-')
        except ValueError:
            raise AuthError('Invalid response, invalid opaque value')

        try:
            received_key = base64.b64decode(received_ekey).decode('ascii')
            received_nonce, received_clientip, received_time = received_key.split(',')
        except ValueError:
            raise AuthError('Invalid response, invalid opaque value')

        if received_nonce != nonce:
            raise AuthError('Invalid response, incompatible opaque/nonce values')

        if received_clientip != clientip:
            raise AuthError('Invalid response, incompatible opaque/client values')

        try:
            received_time = int(received_time)
        except ValueError:
            raise AuthError('Invalid response, invalid opaque/time values')

        expired = (time.time() - received_time) > self.DIGEST_CHALLENGE_TIMEOUT_SECONDS
        if expired:
            raise AuthError('Invalid response, incompatible opaque/nonce too old')

        digest = hexdigest_str(received_key.encode('ascii') + self.DIGEST_PRIVATE_KEY)
        if received_digest != digest:
            raise AuthError('Invalid response, invalid opaque value')

        return True

    def calculate_expected_response(self, challenge, params):
        algo = params.get('algorithm', 'md5').lower()
        qop  = params.get('qop', 'auth')
        user = params['username']
        realm = params['realm']
        nonce = params['nonce']
        nc = params['nc']
        cnonce = params['cnonce']

        ha1 = self.HA1(algo, user, realm, challenge, nonce, cnonce)
        ha2 = self.HA2(algo, self.request.method, self.request.uri, qop, self.request.body)

        data = (ha1, nonce, nc, cnonce, qop, ha2)
        return hexdigest_str(':'.join(data).encode('ascii'))

    def HA1(self, algorithm, username, realm, password, nonce, cnonce, ):
        data = ':'.join((username, realm, password))
        ha1 = hexdigest_str(data.encode('ascii'))

        if algorithm == 'md5-sess':
            data = ':'.join((ha1, nonce, cnonce))
            ha1 = hexdigest_str(data.encode('ascii'))

        return ha1

    def HA2(self, algorithm, method, digest_uri, qop, body):
        data = [method, digest_uri]
        if qop and qop == 'auth-int':
            data.append(hexdigest_str(body))

        return hexdigest_str(':'.join(data).encode('ascii'))


class BasicAuthMixin(object):
    class SendChallenge(Exception):
        pass

    def get_authenticated_user(self, check_credentials_func, realm):
        try:
            return self.authenticate_user(check_credentials_func, realm)
        except self.SendChallenge:
            self.send_auth_challenge(realm)

    def send_auth_challenge(self, realm):
        hdr = 'Basic realm="%s"' % realm.replace('\\', '\\\\').replace('"', '\\"')
        self.set_status(401)
        self.set_header('www-authenticate', hdr)
        self.finish()
        return False

    def authenticate_user(self, check_credentials_func, realm):
        auth_header = self.request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Basic '):
            raise self.SendChallenge()

        auth_data = auth_header.split(None, 1)[-1]
        auth_data = base64.b64decode(auth_data).decode('ascii')
        username, password = auth_data.split(':', 1)

        challenge = check_credentials_func(username)
        if not challenge:
            raise self.SendChallenge()

        if challenge == password:
            self._current_user = username
            return True
        else:
            raise self.SendChallenge()
        return False


def auth_required(realm, auth_func):
    '''Decorator that protect methods with HTTP authentication.'''
    def auth_decorator(func):
        def inner(self, *args, **kw):
            if self.get_authenticated_user(auth_func, realm):
                return func(self, *args, **kw)
        return inner
    return auth_decorator


__all__ = 'auth_required', 'BasicAuthMixin', 'DigestAuthMixin'
