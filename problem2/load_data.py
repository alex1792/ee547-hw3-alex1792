import boto3
import json
import re
import sys
from collections import Counter
from datetime import datetime

# Stopwords list as specified in requirements
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'can', 'this', 'that', 'these', 'those', 'we', 'our', 'use', 'using',
    'based', 'approach', 'method', 'paper', 'propose', 'proposed', 'show'
}


def extract_keywords(abstract, max_keywords=10):
    """
    Extract top keywords from abstract.
    
    Args:
        abstract: paper's abstract text
        max_keywords: max number of keywords to return
    
    Returns:
        List of top keywords (lowercased)
    """
    if not abstract:
        return []
    
    # Clean and tokenize
    text = abstract.lower()
    # Remove special characters, keep only alphanumeric and spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Split into words
    words = text.split()
    
    # Filter stopwords and short words (< 3 chars)
    words = [w for w in words if w not in STOPWORDS and len(w) >= 3]
    
    # Count frequency
    word_counts = Counter(words)
    
    # Get top N keywords
    top_keywords = [word for word, count in word_counts.most_common(max_keywords)]
    
    return top_keywords


def parse_date(published_str):
    """Extract date from ISO timestamp."""
    try:
        dt = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except:
        return published_str[:10] if len(published_str) >= 10 else published_str


def create_category_item(paper):
    """
    Create main category-based item for DynamoDB.
    Each paper gets one item per category.
    This is the primary item with PK=CATEGORY#{category}, SK={date}#{arxiv_id}
    """
    date_str = parse_date(paper['published'])
    
    # PK: CATEGORY#{category}
    # SK: {date}#{arxiv_id}
    pk = f"CATEGORY#{paper['categories'][0]}"  # Primary category
    sk = f"{date_str}#{paper['arxiv_id']}"
    
    # Extract keywords from abstract
    keywords = extract_keywords(paper['abstract'])
    
    item = {
        'PK': pk,
        'SK': sk,
        'arxiv_id': paper['arxiv_id'],
        'title': paper['title'],
        'authors': paper['authors'],
        'abstract': paper['abstract'],
        'categories': paper['categories'],
        'keywords': keywords,
        'published': paper['published'],
        'updated': paper.get('updated', paper['published'])
    }
    
    return item, keywords


def create_author_items(paper):
    """
    Create author-based items for GSI1.
    Each paper gets duplicated for each author.
    Each author item uses different PK/SK to avoid duplicates in batch writes.
    """
    date_str = parse_date(paper['published'])
    keywords = extract_keywords(paper['abstract'])
    
    items = []
    for author in paper['authors']:
        item = {
            'PK': f"CATEGORY#{paper['categories'][0]}",
            'SK': f"AUTHOR#{author}#{date_str}#{paper['arxiv_id']}",  # Unique SK per author
            'GSI1PK': f"AUTHOR#{author}",
            'GSI1SK': date_str,
            'arxiv_id': paper['arxiv_id'],
            'title': paper['title'],
            'authors': paper['authors'],
            'abstract': paper['abstract'],
            'categories': paper['categories'],
            'keywords': keywords,
            'published': paper['published'],
            'updated': paper.get('updated', paper['published'])
        }
        items.append(item)
    
    return items


def create_keyword_items(paper):
    """
    Create keyword-based items for GSI3.
    Each paper gets duplicated for each keyword.
    Each keyword item uses different PK/SK to avoid duplicates in batch writes.
    """
    date_str = parse_date(paper['published'])
    keywords = extract_keywords(paper['abstract'])
    
    items = []
    for keyword in keywords:
        item = {
            'PK': f"CATEGORY#{paper['categories'][0]}",
            'SK': f"KEYWORD#{keyword}#{date_str}#{paper['arxiv_id']}",  # Unique SK per keyword
            'GSI3PK': f"KEYWORD#{keyword}",
            'GSI3SK': date_str,
            'arxiv_id': paper['arxiv_id'],
            'title': paper['title'],
            'authors': paper['authors'],
            'abstract': paper['abstract'],
            'categories': paper['categories'],
            'keywords': keywords,
            'published': paper['published'],
            'updated': paper.get('updated', paper['published'])
        }
        items.append(item)
    
    return items


def create_paper_by_id_item(paper):
    """
    Create paper ID lookup item for GSI2.
    One item per paper for direct ID lookup.
    Uses different SK to avoid duplicates.
    """
    date_str = parse_date(paper['published'])
    keywords = extract_keywords(paper['abstract'])
    
    item = {
        'PK': f"CATEGORY#{paper['categories'][0]}",
        'SK': f"PAPERID#{paper['arxiv_id']}",  # Unique SK for paper ID lookup
        'GSI2PK': f"PAPER#{paper['arxiv_id']}",
        'GSI2SK': date_str,
        'arxiv_id': paper['arxiv_id'],
        'title': paper['title'],
        'authors': paper['authors'],
        'abstract': paper['abstract'],
        'categories': paper['categories'],
        'keywords': keywords,
        'published': paper['published'],
        'updated': paper.get('updated', paper['published'])
    }
    
    return item


def create_table_and_gsis(dynamodb, table_name):
    """
    Create DynamoDB table with GSIs.
    Returns the table object.
    """
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},   # Partition key
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}   # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},  # Author GSI
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},  # Paper ID GSI
                {'AttributeName': 'GSI2SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI3PK', 'AttributeType': 'S'},  # Keyword GSI
                {'AttributeName': 'GSI3SK', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'AuthorIndex',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'PaperIdIndex',
                    'KeySchema': [
                        {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'KeywordIndex',
                    'KeySchema': [
                        {'AttributeName': 'GSI3PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI3SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand pricing
        )
        print(f"Creating table {table_name}...")
        table.wait_until_exists()
        print(f"Table {table_name} created successfully")
        return table
    except Exception as e:
        if 'ResourceInUseException' in str(e):
            print(f"Table {table_name} already exists, using existing table")
            return dynamodb.Table(table_name)
        else:
            raise e


def batch_write_items(table, items, batch_size=25):
    """
    Write items to DynamoDB in batches.
    DynamoDB BatchWriteItem supports up to 25 items per request.
    """
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


def main():
    # Parse command line arguments
    if len(sys.argv) < 3:
        print("Usage: python load_data.py <papers_json_path> <table_name> [--region REGION]")
        sys.exit(1)
    
    papers_path = sys.argv[1]
    table_name = sys.argv[2]
    region = 'us-east-1'  # default
    
    # Parse optional region argument
    if '--region' in sys.argv:
        idx = sys.argv.index('--region')
        if idx + 1 < len(sys.argv):
            region = sys.argv[idx + 1]
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name=region)
    
    # Create table with GSIs
    create_table_and_gsis(dynamodb, table_name)
    table = dynamodb.Table(table_name)
    
    print(f"Creating GSIs: AuthorIndex, PaperIdIndex, KeywordIndex")
    print(f"Loading papers from {papers_path}...")
    
    # Load papers
    with open(papers_path, 'r') as f:
        papers = json.load(f)
    
    print("Extracting keywords from abstracts...")
    
    # Prepare all items
    all_items = []
    stats = {
        'category_items': 0,
        'author_items': 0,
        'keyword_items': 0,
        'paper_id_items': 0
    }
    
    for paper in papers:
        # Create category item
        cat_item, keywords = create_category_item(paper)
        all_items.append(cat_item)
        stats['category_items'] += 1
        
        # Create author items
        author_items = create_author_items(paper)
        all_items.extend(author_items)
        stats['author_items'] += len(author_items)
        
        # Create keyword items
        keyword_items = create_keyword_items(paper)
        all_items.extend(keyword_items)
        stats['keyword_items'] += len(keyword_items)
        
        # Create paper ID item
        paper_id_item = create_paper_by_id_item(paper)
        all_items.append(paper_id_item)
        stats['paper_id_items'] += 1
    
    # Write to DynamoDB
    print("Writing items to DynamoDB...")
    batch_write_items(table, all_items)
    
    # Print statistics
    print(f"\nLoaded {len(papers)} papers")
    print(f"Created {len(all_items)} DynamoDB items (denormalized)")
    denorm_factor = len(all_items) / len(papers) if papers else 0
    print(f"Denormalization factor: {denorm_factor:.1f}x")
    print("\nStorage breakdown:")
    print(f"  - Category items: {stats['category_items']} ({stats['category_items']/len(papers):.1f} per paper avg)")
    print(f"  - Author items: {stats['author_items']} ({stats['author_items']/len(papers):.1f} per paper avg)")
    print(f"  - Keyword items: {stats['keyword_items']} ({stats['keyword_items']/len(papers):.1f} per paper avg)")
    print(f"  - Paper ID items: {stats['paper_id_items']} ({stats['paper_id_items']/len(papers):.1f} per paper)")


if __name__ == '__main__':
    main()