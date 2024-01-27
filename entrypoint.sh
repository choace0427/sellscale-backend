#!/bin/bash

# Wait for PostgreSQL to be ready
# until pg_isready -h db -p 5432 -U postgres; do
#   echo "Waiting for PostgreSQL to start..."
#   sleep 5
# done

# Start the Flask application
exec flask run --host=0.0.0.0
# exec gunicorn -w 8 -b 0.0.0.0:5000 --timeout 60 app:app