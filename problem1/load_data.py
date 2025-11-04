#!/usr/bin/env python3
"""
Data loading script for transit database.
Loads CSV files into PostgreSQL database in the correct order to handle foreign key dependencies.
"""

import argparse
import csv
import os
import sys
import psycopg2
from psycopg2.extras import execute_values


def connect_db(host, dbname, user, password):
    """Establish connection to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=host,
            database=dbname,
            user=user,
            password=password
        )
        print(f"Connected to {dbname}@{host}")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)


def execute_sql_file(conn, schema_file):
    """Execute SQL file to create schema."""
    if not os.path.exists(schema_file):
        print(f"Error: Schema file not found: {schema_file}", file=sys.stderr)
        sys.exit(1)
    
    print("Creating schema...")
    try:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Execute schema SQL statement by statement
        with conn.cursor() as cur:
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            for statement in statements:
                if statement:
                    cur.execute(statement)
        
        conn.commit()
        print("Tables created: lines, stops, line_stops, trips, stop_events")
    except psycopg2.Error as e:
        print(f"Error creating schema: {e}", file=sys.stderr)
        conn.rollback()
        sys.exit(1)


def load_lines(conn, datadir):
    """Load lines.csv into lines table."""
    csv_path = os.path.join(datadir, 'lines.csv')
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found, skipping...")
        return 0
    
    print(f"Loading {csv_path}...", end=' ')
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            with conn.cursor() as cur:
                rows = []
                for row in reader:
                    rows.append((row['line_name'], row['vehicle_type']))
                
                if rows:
                    execute_values(
                        cur,
                        "INSERT INTO lines (line_name, vehicle_type) VALUES %s",
                        rows
                    )
        
        conn.commit()
        print(f"{len(rows)} rows")
        return len(rows)
    except psycopg2.Error as e:
        print(f"Error loading lines: {e}", file=sys.stderr)
        conn.rollback()
        return 0


def load_stops(conn, datadir):
    """Load stops.csv into stops table."""
    csv_path = os.path.join(datadir, 'stops.csv')
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found, skipping...")
        return 0
    
    print(f"Loading {csv_path}...", end=' ')
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            with conn.cursor() as cur:
                rows = []
                for row in reader:
                    rows.append((
                        row['stop_name'],
                        float(row['latitude']) if row['latitude'] else None,
                        float(row['longitude']) if row['longitude'] else None
                    ))
                
                if rows:
                    execute_values(
                        cur,
                        "INSERT INTO stops (stop_name, latitude, longitude) VALUES %s",
                        rows
                    )
        
        conn.commit()
        print(f"{len(rows)} rows")
        return len(rows)
    except psycopg2.Error as e:
        print(f"Error loading stops: {e}", file=sys.stderr)
        conn.rollback()
        return 0


def load_line_stops(conn, datadir):
    """Load line_stops.csv into line_stops table."""
    csv_path = os.path.join(datadir, 'line_stops.csv')
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found, skipping...")
        return 0
    
    print(f"Loading {csv_path}...", end=' ')
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            with conn.cursor() as cur:
                rows = []
                seen_keys = set()  # Track seen (line_id, stop_id) pairs to avoid duplicates
                skipped_duplicates = []
                skipped_fk = []
                for row in reader:
                    # Get line_id and stop_id from foreign key lookups
                    line_id, stop_id = get_line_stop_ids(cur, row['line_name'], row['stop_name'])
                    if line_id and stop_id:
                        key = (line_id, stop_id)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            rows.append((
                                line_id,
                                stop_id,
                                int(row['sequence']),
                                int(row['time_offset'])
                            ))
                        else:
                            skipped_duplicates.append((row['line_name'], row['stop_name'], row['sequence']))
                    else:
                        skipped_fk.append((row['line_name'], row['stop_name'], line_id is None, stop_id is None))
                
                if skipped_duplicates:
                    print(f"\nWarning: Skipped {len(skipped_duplicates)} duplicate (line_id, stop_id) rows")
                
                if skipped_fk:
                    print(f"\nWarning: Skipped {len(skipped_fk)} rows due to missing foreign keys:")
                    for line_name, stop_name, no_line, no_stop in skipped_fk[:10]:  # Show first 10
                        reason = []
                        if no_line:
                            reason.append("line not found")
                        if no_stop:
                            reason.append("stop not found")
                        print(f"  {line_name} / {stop_name}: {', '.join(reason)}")
                
                if rows:
                    execute_values(
                        cur,
                        "INSERT INTO line_stops (line_id, stop_id, sequence_number, time_offset_minutes) VALUES %s",
                        rows
                    )
        
        conn.commit()
        print(f"{len(rows)} rows")
        return len(rows)
    except psycopg2.Error as e:
        print(f"Error loading line_stops: {e}", file=sys.stderr)
        conn.rollback()
        return 0
    except (ValueError, KeyError) as e:
        print(f"Error parsing line_stops CSV: {e}", file=sys.stderr)
        print(f"Row: {row}", file=sys.stderr)
        return 0


def load_trips(conn, datadir):
    """Load trips.csv into trips table."""
    csv_path = os.path.join(datadir, 'trips.csv')
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found, skipping...")
        return 0
    
    print(f"Loading {csv_path}...", end=' ')
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            with conn.cursor() as cur:
                rows = []
                for row in reader:
                    # Get line_id from line_name
                    line_id = get_line_id(cur, row['line_name'])
                    if line_id:
                        rows.append((
                            row['trip_id'],
                            line_id,
                            row['scheduled_departure'],
                            row['vehicle_id']
                        ))
                
                if rows:
                    execute_values(
                        cur,
                        "INSERT INTO trips (trip_id, line_id, scheduled_start_time, vehicle_id) VALUES %s",
                        rows
                    )
        
        conn.commit()
        print(f"{len(rows)} rows")
        return len(rows)
    except psycopg2.Error as e:
        print(f"Error loading trips: {e}", file=sys.stderr)
        conn.rollback()
        return 0


def load_stop_events(conn, datadir):
    """Load stop_events.csv into stop_events table."""
    csv_path = os.path.join(datadir, 'stop_events.csv')
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found, skipping...")
        return 0
    
    print(f"Loading {csv_path}...", end=' ')
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            with conn.cursor() as cur:
                rows = []
                seen_keys = set()  # Track seen (trip_id, stop_id) pairs to avoid duplicates
                skipped_duplicates = []
                for row in reader:
                    # Get stop_id from stop_name (trip_id is already in correct format)
                    stop_id = get_stop_id(cur, row['stop_name'])
                    if stop_id:
                        key = (row['trip_id'], stop_id)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            rows.append((
                                row['trip_id'],  # Use trip_id directly from CSV
                                stop_id,
                                row['scheduled'],
                                row['actual'],
                                int(row['passengers_on']),
                                int(row['passengers_off'])
                            ))
                        else:
                            skipped_duplicates.append((row['trip_id'], row['stop_name']))
                    # Note: We don't track missing stops separately here, but could if needed
                
                if skipped_duplicates:
                    print(f"\nWarning: Skipped {len(skipped_duplicates)} duplicate (trip_id, stop_id) rows")
                
                if rows:
                    execute_values(
                        cur,
                        "INSERT INTO stop_events (trip_id, stop_id, scheduled_arrival_time, actual_arrival_time, passengers_on, passengers_off) VALUES %s",
                        rows
                    )
        
        conn.commit()
        print(f"{len(rows)} rows")
        return len(rows)
    except psycopg2.Error as e:
        print(f"Error loading stop_events: {e}", file=sys.stderr)
        conn.rollback()
        return 0
    except (ValueError, KeyError) as e:
        print(f"Error parsing stop_events CSV: {e}", file=sys.stderr)
        print(f"Row: {row}", file=sys.stderr)
        return 0


def get_line_id(cursor, line_name):
    """Get line_id from line_name."""
    cursor.execute("SELECT line_id FROM lines WHERE line_name = %s", (line_name,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_stop_id(cursor, stop_name):
    """Get stop_id from stop_name."""
    cursor.execute("SELECT stop_id FROM stops WHERE stop_name = %s", (stop_name,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_line_stop_ids(cursor, line_name, stop_name):
    """Get both line_id and stop_id from their names."""
    cursor.execute("SELECT line_id FROM lines WHERE line_name = %s", (line_name,))
    line_result = cursor.fetchone()
    line_id = line_result[0] if line_result else None
    
    cursor.execute("SELECT stop_id FROM stops WHERE stop_name = %s", (stop_name,))
    stop_result = cursor.fetchone()
    stop_id = stop_result[0] if stop_result else None
    
    return line_id, stop_id


def main():
    parser = argparse.ArgumentParser(description='Load transit data into PostgreSQL')
    parser.add_argument('--host', required=True, help='Database host')
    parser.add_argument('--dbname', required=True, help='Database name')
    parser.add_argument('--user', required=True, help='Database user')
    parser.add_argument('--password', required=True, help='Database password')
    parser.add_argument('--datadir', default='data', help='Directory containing CSV files (default: data)')
    parser.add_argument('--schema', default='schema.sql', help='Schema SQL file (default: schema.sql)')
    
    args = parser.parse_args()
    
    # Connect to database
    conn = connect_db(args.host, args.dbname, args.user, args.password)
    
    # Create schema
    execute_sql_file(conn, args.schema)
    
    # Load data in order (respecting foreign key dependencies)
    total_rows = 0
    total_rows += load_lines(conn, args.datadir)
    total_rows += load_stops(conn, args.datadir)
    total_rows += load_line_stops(conn, args.datadir)
    total_rows += load_trips(conn, args.datadir)
    total_rows += load_stop_events(conn, args.datadir)
    
    # Print summary
    print(f"\nTotal: {total_rows:,} rows loaded")
    
    conn.close()


if __name__ == '__main__':
    main()
