from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config.settings import JWT_SECRET
from src.models.database import connect
from src.utils.passwords import verify_password

bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = '00000000000000000000000000000000:' + '0' * 128


def login(data):
    with connect() as db:
        account = db.execute('SELECT * FROM accounts WHERE username = %s', (data.username,)).fetchone()
    valid = verify_password(data.password, account['password_hash'] if account else DUMMY_HASH)
    if not account or not valid:
        raise HTTPException(401, '账号或密码不正确')
    account.pop('password_hash')
    token = jwt.encode({'sub': account['username'], 'exp': datetime.now(timezone.utc) + timedelta(hours=8)},
                       JWT_SECRET, algorithm='HS256')
    return {'token': token, 'user': account}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, '请先登录')
    try:
        username = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=['HS256'],
                              options={'require': ['exp', 'sub']})['sub']
    except jwt.InvalidTokenError:
        raise HTTPException(401, '会话已过期，请重新登录') from None
    with connect() as db:
        account = db.execute('SELECT username, display_name, role FROM accounts WHERE username = %s',
                             (username,)).fetchone()
    if not account:
        raise HTTPException(401, '账号已停用')
    return account


def require_role(role):
    def permitted(user=Depends(current_user)):
        if user['role'] != role:
            raise HTTPException(403, '当前角色无权执行此操作')
        return user
    return permitted
