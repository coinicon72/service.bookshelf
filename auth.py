from flask import request
from sqlalchemy.exc import IntegrityError, DatabaseError

from dao import Token


def generate_token():
    '''use os.urandom to generate a 16 bytes (32 chars) token'''
    return ''.join('{:02x}'.format(x) for x in os.urandom(16))


def check_bearer_token(auth):
    '''get token from query string and check for expiration'''
    if auth is None:
        raise RuntimeError({'result':-30, 'msg':'token not found'})

    if not auth.startswith('Bearer'):
        raise RuntimeError({'result':-30, 'msg':'token not found'})

    str_tokens = auth.split(' ')
    if len(str_tokens) < 2:
        raise RuntimeError({'result':-30, 'msg':'token not found'})

    str_token = str_tokens[1]
    token = Token.query.filter_by(token=str_token).first()
    if token is None:
        raise RuntimeError({'result':-30, 'msg':'token not found'})

    if token.user is None:
        raise RuntimeError({'result':-41, 'msg':'user not exist'})

    if token.is_expired():
        try:
            db.session.delete(token)
            db.session.commit()
        except DatabaseError:
            db.session.rollback()

        raise RuntimeError({'result':-31, 'msg':'token expired'})
    
    return token.user


def TokenCheck(func):
    '''decorator to check bearer token'''

    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization')
        try:
            user = check_bearer_token(auth)
            return func(*args, **kwargs, user=user)
        except RuntimeError as e:
            return e.args[0]

    return wrapper