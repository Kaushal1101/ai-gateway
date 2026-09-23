#!/bin/bash
set -e

PGDATA=/var/lib/postgresql/data

if [ ! -f "$PGDATA/PG_VERSION" ]; then
    # Wipe any partial state from a previous interrupted bootstrap before
    # retrying — checking only for PG_VERSION means a half-written directory
    # would skip this block and fail to start.
    rm -rf "$PGDATA"/*  "$PGDATA"/.[!.]*  2>/dev/null || true
    chown postgres:postgres "$PGDATA"
    chmod 700 "$PGDATA"

    export PGPASSWORD=postgres
    echo "Bootstrapping replica from primary..."
    until gosu postgres pg_basebackup \
        -h postgres \
        -U postgres \
        -D "$PGDATA" \
        -Fp -Xs -P -R; do
        echo "Primary not ready — retrying in 2s..."
        rm -rf "$PGDATA"
        mkdir -p "$PGDATA"
        chown postgres:postgres "$PGDATA"
        chmod 700 "$PGDATA"
        sleep 2
    done
fi

exec gosu postgres postgres
