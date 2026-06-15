#!/bin/bash
echo "creating DB tables..."
python -c "from database import engine; import db_models; db_models.Base.metadata.create_all(bind=engine)"
exec "$@"