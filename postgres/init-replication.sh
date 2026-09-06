#!/bin/bash
# Runs once on first database initialization (empty data dir).
# Appends a replication entry to pg_hba.conf so the replica can connect.
echo "host replication postgres all scram-sha-256" >> "$PGDATA/pg_hba.conf"
