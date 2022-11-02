FROM debian:bookworm

# prepare
ENV LANG C.UTF-8
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update -qq

# set up Postgres with debversion extension for use in Laniakea testssuite
RUN apt-get install --no-install-recommends -yq \
    postgresql-15 \
    postgresql-15-debversion

RUN echo "/etc/init.d/postgresql start && exit 0" > /etc/rc.local
RUN /etc/init.d/postgresql start && \
    su postgres -c "psql -c \"CREATE USER lkdbuser_test WITH PASSWORD 'notReallySecret';\"" && \
    su postgres -c "psql -c \"CREATE DATABASE laniakea_unittest WITH OWNER lkdbuser_test;\"" && \
    su postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE laniakea_unittest TO lkdbuser_test;\"" && \
    su postgres -c "psql -c \"CREATE EXTENSION IF NOT EXISTS debversion;\" laniakea_unittest"

USER postgres
RUN echo "host all  all    0.0.0.0/0  md5" >> /etc/postgresql/15/main/pg_hba.conf

RUN echo "listen_addresses = '*'" >> /etc/postgresql/15/main/postgresql.conf
RUN echo "log_destination = 'stderr'" >> /etc/postgresql/15/main/postgresql.conf

EXPOSE 5434
CMD ["/usr/lib/postgresql/15/bin/postgres", "-D", "/var/lib/postgresql/15/main", "-c", "config_file=/etc/postgresql/15/main/postgresql.conf", "-p", "5432"]
