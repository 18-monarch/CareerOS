from alembic import context
from careeros import models  # noqa: F401
from careeros.config import get_settings
from careeros.db import Base, build_engine

config = context.config
target_metadata = Base.metadata
url = get_settings().database_url
if context.is_offline_mode():
    context.configure(
        url=url.replace("postgresql://", "postgresql+psycopg://"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    connectable = build_engine(url)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
