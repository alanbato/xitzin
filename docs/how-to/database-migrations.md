# Database Migrations

This guide covers database schema migrations for Xitzin applications using SQLModel and Alembic.

!!! note "Prerequisites"
    This guide assumes you have SQLModel set up. See the [SQLModel reference](../reference/sqlmodel.md) for installation and basic usage.

## Why Migrations?

The `init_db()` function creates tables from your models, but it cannot:

- Add columns to existing tables
- Rename or remove columns
- Change column types
- Preserve existing data during schema changes

For production applications, you need a migration tool. **Alembic** is the standard migration tool for SQLAlchemy (which SQLModel is built on).

## Setting Up Alembic

### Install Alembic

```bash
uv add alembic
```

### Initialize Alembic

```bash
alembic init migrations
```

This creates:

```
migrations/
├── env.py          # Migration environment config
├── script.py.mako  # Migration template
└── versions/       # Migration files go here
alembic.ini         # Alembic configuration
```

### Configure the Database URL

Edit `alembic.ini`:

```ini
# alembic.ini
sqlalchemy.url = sqlite:///./data/app.db
```

!!! tip "Environment Variables"
    For production, use environment variables instead of hardcoding:

    ```ini
    sqlalchemy.url = %(DATABASE_URL)s
    ```

    Then set `DATABASE_URL` in your environment.

### Configure Model Metadata

Edit `migrations/env.py` to import your models:

```python
# migrations/env.py
from sqlmodel import SQLModel

# Import all your models so Alembic can detect them
from your_app.models import User, Post, Comment  # adjust imports

target_metadata = SQLModel.metadata
```

## Creating Migrations

### Auto-generate from Model Changes

When you modify a model, generate a migration:

```bash
alembic revision --autogenerate -m "Add karma column to User"
```

This detects changes and creates a migration file:

```
INFO  [alembic.autogenerate.compare] Detected added column 'user.karma'
  Generating migrations/versions/a1b2c3d4_add_karma_column_to_user.py
```

### Review the Generated Migration

Always review auto-generated migrations before applying:

```python
# migrations/versions/a1b2c3d4_add_karma_column_to_user.py
"""Add karma column to User

Revision ID: a1b2c3d4
Revises:
Create Date: 2024-01-15 10:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('karma', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('user', 'karma')
```

### Manual Migrations

For complex changes, create an empty migration:

```bash
alembic revision -m "Migrate user data"
```

Then write the migration logic manually:

```python
def upgrade():
    # Add new column
    op.add_column('user', sa.Column('display_name', sa.String(), nullable=True))

    # Copy data from old column
    op.execute("UPDATE user SET display_name = username")

    # Make non-nullable after populating
    op.alter_column('user', 'display_name', nullable=False)


def downgrade():
    op.drop_column('user', 'display_name')
```

## Running Migrations

### Apply All Pending Migrations

```bash
alembic upgrade head
```

### Apply to a Specific Revision

```bash
alembic upgrade a1b2c3d4
```

### Rollback One Migration

```bash
alembic downgrade -1
```

### Rollback to a Specific Revision

```bash
alembic downgrade a1b2c3d4
```

### View Current Revision

```bash
alembic current
```

### View Migration History

```bash
alembic history
```

## Example Workflow

Here's a complete example of adding a new field to a model.

### 1. Update Your Model

```python
# models.py
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    fingerprint: str = Field(unique=True, index=True)
    username: str | None = None
    karma: int = Field(default=0)  # NEW FIELD
```

### 2. Generate Migration

```bash
$ alembic revision --autogenerate -m "Add karma to users"
INFO  [alembic.autogenerate.compare] Detected added column 'user.karma'
  Generating migrations/versions/a1b2c3d4_add_karma_to_users.py
```

### 3. Review and Edit

```python
# migrations/versions/a1b2c3d4_add_karma_to_users.py
def upgrade():
    op.add_column('user', sa.Column('karma', sa.Integer(), nullable=True))
    # Set default for existing rows
    op.execute("UPDATE user SET karma = 0 WHERE karma IS NULL")


def downgrade():
    op.drop_column('user', 'karma')
```

### 4. Apply Migration

```bash
$ alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> a1b2c3d4, Add karma to users
```

## Running Migrations on Startup

You can run migrations automatically when your application starts:

```python
from alembic.config import Config
from alembic import command

@app.on_startup
async def run_migrations():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

!!! warning "Use with Caution"
    Auto-migration on startup can be dangerous in production:

    - Migrations may fail, preventing app startup
    - Concurrent deployments may conflict
    - No opportunity to review changes

    Consider running migrations explicitly as part of your deployment process instead.

## Testing with Migrations

### Test Database Setup

Use a separate test database and apply migrations before tests:

```python
# conftest.py
import pytest
from sqlmodel import create_engine, SQLModel
from alembic.config import Config
from alembic import command

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine("sqlite:///./test.db")

    # Run migrations
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", "sqlite:///./test.db")
    command.upgrade(alembic_cfg, "head")

    yield engine

    # Cleanup
    import os
    os.remove("test.db")
```

### Reset Database Between Tests

```python
@pytest.fixture
def session(test_engine):
    from sqlmodel import Session

    with Session(test_engine) as session:
        yield session
        session.rollback()
```

## Common Operations

### Add a Column

```python
def upgrade():
    op.add_column('user', sa.Column('email', sa.String(255), nullable=True))
```

### Remove a Column

```python
def upgrade():
    op.drop_column('user', 'legacy_field')
```

### Rename a Column

```python
def upgrade():
    op.alter_column('user', 'score', new_column_name='points')
```

### Add an Index

```python
def upgrade():
    op.create_index('ix_user_email', 'user', ['email'])
```

### Create a New Table

```python
def upgrade():
    op.create_table(
        'post',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id')),
    )
```

## Further Reading

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
