from arq.connections import RedisSettings

from app.config import get_settings
from app.workers.tasks import ping, process_load_data

settings = get_settings()


class WorkerSettings:
    functions = [ping, process_load_data]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
