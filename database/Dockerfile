FROM postgres:15-alpine

# Copy the init script directly into the container image directory
COPY init.sql /docker-entrypoint-initdb.d/init.sql

# Explicitly guarantee the file has the correct permissions and LF line endings
RUN chmod 644 /docker-entrypoint-initdb.d/init.sql