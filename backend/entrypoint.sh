#!/bin/bash
set -e

echo "⏳ Waiting for database..."
while ! python -c "
import os, asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.connect() as c:
        await c.execute(text('SELECT 1'))
    await engine.dispose()

asyncio.run(check())
" 2>/dev/null; do
    echo "Database not ready, retrying in 2s..."
    sleep 2
done

echo "✅ Database is ready"

if echo "$@" | grep -q "celery"; then
    echo "⚙️  Celery worker — skipping migrations (handled by backend)"
else
    echo "⏳ Running migrations..."
    alembic upgrade head
    echo "✅ Migrations complete"
fi

echo "🚀 Starting application..."
exec "$@"