from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.middlewares.http import error_boundary, response_headers
from src.models.database import cache, connect
from src.routes.api import api

app = FastAPI(title='平渡展陈 · 易读展签复验')
app.middleware('http')(error_boundary)
app.middleware('http')(response_headers)
app.include_router(api)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = '、'.join(dict.fromkeys(str(item['loc'][-1]) for item in exc.errors()))
    return JSONResponse({'detail': f'请检查字段 {fields}'}, status_code=422)


@app.get('/health')
@app.get('/api/health')
def health():
    with connect() as db:
        db.execute('SELECT 1 FROM schema_migrations LIMIT 1')
    cache.ping()
    return {'status': 'ok'}
