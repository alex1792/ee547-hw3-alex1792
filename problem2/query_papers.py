#!/usr/bin/env python3
"""
Query ArXiv papers from DynamoDB.
Implements 5 query patterns with JSON output.
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError


def query_recent_in_category(table_name, category, limit=20, region='us-east-1'):
    """
    Query 1: Browse recent papers in category.
    Uses: Main table partition key query with sort key descending.
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    try:
        # Use pagination to ensure we get enough results after filtering
        items = []
        last_key = None
        max_queries = 10  # Prevent infinite loops
        query_count = 0
        
        while query_count < max_queries:
            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {
                    ':pk': f'CATEGORY#{category}'
                },
                'ScanIndexForward': True,  # Ascending order (dates first)
                'Limit': 100  # Query in chunks
            }
            if last_key:
                query_params['ExclusiveStartKey'] = last_key
            
            response = table.query(**query_params)
            batch_items = response.get('Items', [])
            items.extend(batch_items)
            query_count += 1
            
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break  # No more pages
        
        # Filter to only include category items (SK starts with YYYY-MM-DD date format)
        filtered = []
        for item in items:
            sk = item.get('SK', '')
            # Check if SK starts with date pattern YYYY-MM-DD
            if sk and sk[0].isdigit() and len(sk) >= 10 and sk[4] == '-' and sk[7] == '-':
                filtered.append(item)
        
        # Reverse to get most recent first, then take limit
        filtered.reverse()
        
        return filtered[:limit]
    except ClientError as e:
        print(f"Error querying recent papers in category {category}: {e}", file=sys.stderr)
        return []


def query_papers_by_author(table_name, author_name, region='us-east-1'):
    """
    Query 2: Find all papers by author.
    Uses: GSI1 (AuthorIndex) partition key query.
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    try:
        response = table.query(
            IndexName='AuthorIndex',
            KeyConditionExpression='GSI1PK = :author_pk',
            ExpressionAttributeValues={
                ':author_pk': f'AUTHOR#{author_name}'
            }
        )
        return response.get('Items', [])
    except ClientError as e:
        print(f"Error querying papers by author {author_name}: {e}", file=sys.stderr)
        return []


def get_paper_by_id(table_name, arxiv_id, region='us-east-1'):
    """
    Query 3: Get specific paper by ID.
    Uses: GSI2 (PaperIdIndex) for direct lookup.
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    try:
        response = table.query(
            IndexName='PaperIdIndex',
            KeyConditionExpression='GSI2PK = :paper_pk',
            ExpressionAttributeValues={
                ':paper_pk': f'PAPER#{arxiv_id}'
            }
        )
        items = response.get('Items', [])
        return items[0] if items else None
    except ClientError as e:
        print(f"Error getting paper by ID {arxiv_id}: {e}", file=sys.stderr)
        return None


def query_papers_in_date_range(table_name, category, start_date, end_date, region='us-east-1'):
    """
    Query 4: Papers in category within date range.
    Uses: Main table with composite sort key range query.
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    try:
        # Query all items in date range
        response = table.query(
            KeyConditionExpression='PK = :pk AND SK BETWEEN :start AND :end',
            ExpressionAttributeValues={
                ':pk': f'CATEGORY#{category}',
                ':start': f'{start_date}#',
                ':end': f'{end_date}#zzzzzzz'  # Ensure we capture all items on end_date
            }
        )
        items = response.get('Items', [])
        
        # Filter to only include category items (SK starts with YYYY-MM-DD)
        filtered = []
        for item in items:
            sk = item.get('SK', '')
            # Check if SK starts with date pattern YYYY-MM-DD
            if sk and sk[0].isdigit() and len(sk) >= 10 and sk[4] == '-' and sk[7] == '-':
                # Extract date and verify it's within range
                item_date = sk.split('#')[0]
                if start_date <= item_date <= end_date:
                    filtered.append(item)
        
        return filtered
    except ClientError as e:
        print(f"Error querying papers in date range: {e}", file=sys.stderr)
        return []


def query_papers_by_keyword(table_name, keyword, limit=20, region='us-east-1'):
    """
    Query 5: Papers containing keyword.
    Uses: GSI3 (KeywordIndex) partition key query.
    """
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    try:
        response = table.query(
            IndexName='KeywordIndex',
            KeyConditionExpression='GSI3PK = :keyword_pk',
            ExpressionAttributeValues={
                ':keyword_pk': f'KEYWORD#{keyword.lower()}'
            },
            ScanIndexForward=False,  # Most recent first
            Limit=limit
        )
        return response.get('Items', [])
    except ClientError as e:
        print(f"Error querying papers by keyword {keyword}: {e}", file=sys.stderr)
        return []


def format_results(query_type, params, results, execution_time):
    """Format query results as JSON output."""
    output = {
        "query_type": query_type,
        "parameters": params,
        "results": results,
        "count": len(results),
        "execution_time_ms": execution_time
    }
    return json.dumps(output, indent=2, default=str)


def main():
    import time
    
    if len(sys.argv) < 3:
        print("Usage: python query_papers.py <command> <args> [--table TABLE] [--region REGION]")
        print("\nCommands:")
        print("  recent <category> [--limit N]")
        print("  author <author_name>")
        print("  get <arxiv_id>")
        print("  daterange <category> <start_date> <end_date>")
        print("  keyword <keyword> [--limit N]")
        sys.exit(1)
    
    # Parse command
    command = sys.argv[1]
    
    # Parse optional arguments
    table_name = 'arxiv-papers'  # default
    region = 'us-east-1'  # default
    limit = 20  # default
    
    if '--table' in sys.argv:
        idx = sys.argv.index('--table')
        if idx + 1 < len(sys.argv):
            table_name = sys.argv[idx + 1]
    
    if '--region' in sys.argv:
        idx = sys.argv.index('--region')
        if idx + 1 < len(sys.argv):
            region = sys.argv[idx + 1]
    
    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])
    
    # Execute query
    start_time = time.time() * 1000  # milliseconds
    
    if command == 'recent':
        if len(sys.argv) < 3:
            print("Error: category required for recent query", file=sys.stderr)
            sys.exit(1)
        category = sys.argv[2]
        results = query_recent_in_category(table_name, category, limit, region)
        params = {"category": category, "limit": limit}
        
    elif command == 'author':
        if len(sys.argv) < 3:
            print("Error: author name required", file=sys.stderr)
            sys.exit(1)
        author_name = sys.argv[2]
        results = query_papers_by_author(table_name, author_name, region)
        params = {"author": author_name}
        
    elif command == 'get':
        if len(sys.argv) < 3:
            print("Error: arxiv_id required", file=sys.stderr)
            sys.exit(1)
        arxiv_id = sys.argv[2]
        result = get_paper_by_id(table_name, arxiv_id, region)
        results = [result] if result else []
        params = {"arxiv_id": arxiv_id}
        
    elif command == 'daterange':
        if len(sys.argv) < 5:
            print("Error: category, start_date, and end_date required", file=sys.stderr)
            sys.exit(1)
        category = sys.argv[2]
        start_date = sys.argv[3]
        end_date = sys.argv[4]
        results = query_papers_in_date_range(table_name, category, start_date, end_date, region)
        params = {"category": category, "start": start_date, "end": end_date}
        
    elif command == 'keyword':
        if len(sys.argv) < 3:
            print("Error: keyword required", file=sys.stderr)
            sys.exit(1)
        keyword = sys.argv[2]
        results = query_papers_by_keyword(table_name, keyword, limit, region)
        params = {"keyword": keyword, "limit": limit}
        
    else:
        print(f"Error: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)
    
    execution_time = int(time.time() * 1000 - start_time)
    
    # Format and print results
    output = format_results(command, params, results, execution_time)
    print(output)


if __name__ == '__main__':
    main()