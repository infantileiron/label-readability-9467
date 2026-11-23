import logging
from uuid import uuid4

from fastapi.responses import JSONResponse

logger = logging.getLogger('label_readability')


async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Request-ID'] = uuid4().hex
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


async def error_boundary(request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception('Request failed: %s %s', request.method, request.url.path)
        return JSONResponse({'detail': '服务暂不可用，请稍后重试'}, status_code=503)
