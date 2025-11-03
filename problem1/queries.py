#!/usr/bin/env python3
"""
Query implementation for transit database.
Supports 10 SQL queries with JSON output format.
"""

import argparse
import json
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


def connect_db(host, dbname, user, password=''):
    """Establish connection to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=host,
            database=dbname,
            user=user,
            password=password
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)


def execute_query(conn, query, description):
    """Execute a query and return results as JSON."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
            
            # Convert Decimal/DateTime to strings for JSON serialization
            result_list = []
            for row in rows:
                dict_row = {}
                for key, value in row.items():
                    if value is None:
                        dict_row[key] = None
                    else:
                        dict_row[key] = str(value)
                result_list.append(dict_row)
            
            return {
                "query": description["id"],
                "description": description["text"],
                "results": result_list,
                "count": len(result_list)
            }
    except psycopg2.Error as e:
        print(f"Error executing query {description['id']}: {e}", file=sys.stderr)
        return {
            "query": description["id"],
            "description": description["text"],
            "results": [],
            "count": 0,
            "error": str(e)
        }


def get_query_definitions():
    """Define all 10 queries with SQL and descriptions."""
    queries = {
        "Q1": {
            "id": "Q1",
            "text": "List all stops on Route 20 in order",
            "sql": """
                SELECT s.stop_name, ls.sequence_number as sequence, ls.time_offset_minutes as time_offset
                FROM line_stops ls
                JOIN lines l ON ls.line_id = l.line_id
                JOIN stops s ON ls.stop_id = s.stop_id
                WHERE l.line_name = 'Route 20'
                ORDER BY ls.sequence_number;
            """
        },
        "Q2": {
            "id": "Q2",
            "text": "Trips during morning rush (7-9 AM)",
            "sql": """
                SELECT t.trip_id, l.line_name, t.scheduled_start_time as scheduled_departure
                FROM trips t
                JOIN lines l ON t.line_id = l.line_id
                WHERE EXTRACT(HOUR FROM t.scheduled_start_time) >= 7 
                  AND EXTRACT(HOUR FROM t.scheduled_start_time) < 9
                ORDER BY t.scheduled_start_time;
            """
        },
        "Q3": {
            "id": "Q3",
            "text": "Transfer stops (stops on 2+ routes)",
            "sql": """
                SELECT s.stop_name, COUNT(DISTINCT ls.line_id) as line_count
                FROM stops s
                JOIN line_stops ls ON s.stop_id = ls.stop_id
                GROUP BY s.stop_id, s.stop_name
                HAVING COUNT(DISTINCT ls.line_id) >= 2
                ORDER BY line_count DESC, s.stop_name;
            """
        },
        "Q4": {
            "id": "Q4",
            "text": "Complete route for trip T0001",
            "sql": """
                SELECT s.stop_name, ls.sequence_number as sequence
                FROM line_stops ls
                JOIN stops s ON ls.stop_id = s.stop_id
                JOIN lines l ON ls.line_id = l.line_id
                JOIN trips t ON l.line_id = t.line_id
                WHERE t.trip_id = 'T0001'
                ORDER BY sequence;
            """
        },
        "Q5": {
            "id": "Q5",
            "text": "Routes serving both Wilshire / Veteran and Le Conte / Broxton",
            "sql": """
                SELECT l.line_name
                FROM lines l
                WHERE l.line_id IN (
                    SELECT ls1.line_id
                    FROM line_stops ls1
                    JOIN stops s1 ON ls1.stop_id = s1.stop_id
                    WHERE s1.stop_name = 'Wilshire / Veteran'
                )
                AND l.line_id IN (
                    SELECT ls2.line_id
                    FROM line_stops ls2
                    JOIN stops s2 ON ls2.stop_id = s2.stop_id
                    WHERE s2.stop_name = 'Le Conte / Broxton'
                )
                ORDER BY l.line_name;
            """
        },
        "Q6": {
            "id": "Q6",
            "text": "Average ridership by line",
            "sql": """
                SELECT l.line_name, 
                       COALESCE(AVG(se.passengers_on + se.passengers_off), 0) as avg_passengers
                FROM lines l
                JOIN trips t ON l.line_id = t.line_id
                JOIN stop_events se ON t.trip_id = se.trip_id
                GROUP BY l.line_id, l.line_name
                ORDER BY avg_passengers DESC;
            """
        },
        "Q7": {
            "id": "Q7",
            "text": "Top 10 busiest stops",
            "sql": """
                SELECT s.stop_name, SUM(se.passengers_on + se.passengers_off) as total_activity
                FROM stops s
                JOIN stop_events se ON s.stop_id = se.stop_id
                GROUP BY s.stop_id, s.stop_name
                ORDER BY total_activity DESC
                LIMIT 10;
            """
        },
        "Q8": {
            "id": "Q8",
            "text": "Count delays by line (>2 min late)",
            "sql": """
                SELECT l.line_name, COUNT(*) as delay_count
                FROM lines l
                JOIN trips t ON l.line_id = t.line_id
                JOIN stop_events se ON t.trip_id = se.trip_id
                WHERE se.actual_arrival_time > se.scheduled_arrival_time + INTERVAL '2 minutes'
                GROUP BY l.line_id, l.line_name
                ORDER BY delay_count DESC;
            """
        },
        "Q9": {
            "id": "Q9",
            "text": "Trips with 3+ delayed stops",
            "sql": """
                SELECT t.trip_id, COUNT(*) as delayed_stop_count
                FROM trips t
                JOIN stop_events se ON t.trip_id = se.trip_id
                WHERE se.actual_arrival_time > se.scheduled_arrival_time + INTERVAL '2 minutes'
                GROUP BY t.trip_id
                HAVING COUNT(*) >= 3
                ORDER BY delayed_stop_count DESC, t.trip_id;
            """
        },
        "Q10": {
            "id": "Q10",
            "text": "Stops with above-average ridership",
            "sql": """
                SELECT s.stop_name, SUM(se.passengers_on) as total_boardings
                FROM stops s
                JOIN stop_events se ON s.stop_id = se.stop_id
                GROUP BY s.stop_id, s.stop_name
                HAVING SUM(se.passengers_on) > (
                    SELECT AVG(total)
                    FROM (
                        SELECT SUM(passengers_on) as total
                        FROM stop_events
                        GROUP BY stop_id
                    ) as stop_totals
                )
                ORDER BY total_boardings DESC;
            """
        }
    }
    return queries


def main():
    parser = argparse.ArgumentParser(description='Execute SQL queries on transit database')
    parser.add_argument('--query', help='Query ID to execute (Q1-Q10)')
    parser.add_argument('--all', action='store_true', help='Execute all queries')
    parser.add_argument('--host', default='localhost', help='Database host (default: localhost)')
    parser.add_argument('--dbname', required=True, help='Database name')
    parser.add_argument('--user', default='postgres', help='Database user (default: postgres)')
    parser.add_argument('--password', default='', help='Database password')
    parser.add_argument('--format', default='json', choices=['json'], help='Output format (default: json)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.query and not args.all:
        print("Error: Must specify either --query or --all", file=sys.stderr)
        sys.exit(1)
    
    if args.query and args.all:
        print("Error: Cannot specify both --query and --all", file=sys.stderr)
        sys.exit(1)
    
    # Connect to database
    conn = connect_db(args.host, args.dbname, args.user, args.password)
    
    # Get query definitions
    query_defs = get_query_definitions()
    
    # Execute queries
    if args.all:
        results = []
        for query_id in sorted(query_defs.keys()):
            query_def = query_defs[query_id]
            result = execute_query(conn, query_def["sql"], query_def)
            results.append(result)
        
        # Output all results
        output = {
            "queries": results,
            "total_queries": len(results)
        }
        print(json.dumps(output, indent=2))
    else:
        # Execute single query
        if args.query not in query_defs:
            print(f"Error: Unknown query '{args.query}'. Valid queries: Q1-Q10", file=sys.stderr)
            sys.exit(1)
        
        query_def = query_defs[args.query]
        result = execute_query(conn, query_def["sql"], query_def)
        print(json.dumps(result, indent=2))
    
    conn.close()


if __name__ == '__main__':
    main()

