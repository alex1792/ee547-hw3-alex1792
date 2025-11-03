# Problem 2: ArXiv Papers DynamoDB System

## Part A: Schema Design

### Schema Design Decisions

**Q: Why did you choose your partition key structure?**

I picked `CATEGORY#{primary_category}` as the partition key because:
- Category-based queries are a primary access pattern (Query 1: recent papers in category)
- Ensures uniform data distribution across partitions
- Each category has predictable query volume
- Enables efficient date-based sorting with sort keys

**Q: How many GSIs did you create and why?**

I implemented **3 GSIs**:
1. **AuthorIndex** (GSI1): Enables efficient queries for all papers by a specific author
   - Needed for Query 2: Papers by author
   - Uses `AUTHOR#{author_name}` as partition key with date as sort key

2. **PaperIdIndex** (GSI2): Direct lookups by arXiv ID
   - Needed for Query 3: Get paper by ID
   - Uses `PAPER#{arxiv_id}` as partition key

3. **KeywordIndex** (GSI3): Search papers by keywords
   - Needed for Query 5: Papers by keyword
   - Uses `KEYWORD#{keyword}` as partition key with date as sort key

**Q: What denormalization trade-offs did you make?**

I implemented full denormalization:

**Main Items**:
- Category items: `PK=CATEGORY#{cat}`, `SK={date}#{arxiv_id}`
- Used for browsing recent papers in category and date range queries

**Denormalized Items**:
- Author items: Same PK, `SK=AUTHOR#{author}#{date}#{arxiv_id}` (one per author)
- Keyword items: Same PK, `SK=KEYWORD#{keyword}#{date}#{arxiv_id}` (one per keyword)
- Paper ID items: Same PK, `SK=PAPERID#{arxiv_id}` (one per paper)

**Trade-offs**:
- **Pros**: Fast queries without joins, all data pre-computed, excellent read performance
- **Cons**: ~14x storage overhead, potential data inconsistency, complex writes, large storage costs

## Part B: Data Loading

Keywords are extracted from abstracts using frequency analysis:
- Tokenize and clean text
- Filter stopwords
- Count frequency and select top 10 keywords

## Denormalization Analysis

**Average number of DynamoDB items per paper**: 13.9

**Storage multiplication factor**: 13.9x

**Storage breakdown** (from 100 papers):
- Category items: 100 (1.0 per paper)
- Author items: 207 (2.1 per paper avg)
- Keyword items: 986 (9.9 per paper avg)
- Paper ID items: 100 (1.0 per paper)

**Which access patterns caused the most duplication?**

Keyword items caused the most duplication (9.9x per paper) because:
- Each paper generates 10 top keywords from abstract
- More keywords than authors on average
- Necessary for efficient keyword search without full scans

## Query Limitations

**What queries are NOT efficiently supported by your schema?**

1. **Count total papers by author globally**
   - Would require scanning all AuthorIndex partitions
   - No way to count across all authors without expensive operations

2. **Most cited papers globally**
   - Citation data not in schema
   - Global ranking requires scanning all partitions

3. **Aggregate statistics** (avg, sum, count across partitions)
   - DynamoDB doesn't support SQL aggregations
   - Must fetch all items and compute in application layer

4. **Papers with secondary categories**
   - Schema only uses primary category in PK
   - Querying by other categories requires full table scan

5. **Complex joins**
   - Cannot join data across partitions
   - Requires denormalization or application-level joins

**Why are these difficult in DynamoDB?**

- **No cross-partition queries**: Queries limited to single partition key value
- **No aggregations**: No built-in GROUP BY, COUNT, SUM operations
- **Single access pattern focus**: Schema optimized for specific patterns, sacrifices flexibility
- **No SQL**: No complex WHERE clauses, joins, or subqueries

## When to Use DynamoDB

**When would you choose DynamoDB over PostgreSQL?**

**Choose DynamoDB when**:
1. Highly scalable read workloads with predictable access patterns
2. Need global distribution and low-latency multi-region access
3. Want managed service without database administration
4. Traffic patterns are highly variable requiring auto-scaling
5. Simple data model that fits into access patterns well
6. Microservices architecture with service-per-database model

**Choose PostgreSQL when**:
1. Complex queries with joins, aggregations, and ad-hoc analysis
2. Strong consistency and ACID transactions required
3. Cost-sensitive with predictable workloads
4. Need flexible schema with frequent schema changes
5. Development team comfortable with SQL and relational design

**Key Trade-offs**:

| Aspect | DynamoDB | PostgreSQL |
|--------|----------|------------|
| **Query Flexibility** | Limited to specific patterns | Full SQL power |
| **Scalability** | Automatic, unlimited | Manual, complex |
| **Storage Cost** | Higher (~14x overhead) | Lower (normalized) |
| **Consistency** | Eventually consistent | ACID transactions |
| **Management** | Fully managed | Requires DBA |
| **Multi-region** | Built-in replication | Complex setup |
| **Development Speed** | Fast for simple patterns | Flexible for complex needs |

## EC2 Deployment

**EC2 Instance Details**:
- **Instance Type**: t3.micro
- **OS**: Amazon Linux 2023
- **Public IP**: `107.21.168.50`
- **Region**: us-east-1

**IAM Role ARN**: `arn:aws:iam::ACCOUNT_ID:role/EC2-DynamoDB-Access`
- **Attached Policy**: `AmazonDynamoDBFullAccess`

**Challenges Encountered**:

1. **AWS Credentials**: Initially encountered "Unable to locate credentials" error
   - **Solution**: Attached IAM role to EC2 instance instead of using AWS CLI configuration
   - IAM roles are more secure for EC2 deployments

2. **Security Group Configuration**: Port 8080 had to be explicitly opened
   - Added Custom TCP rule for port 8080 from anywhere (0.0.0.0/0)

3. **URL Encoding**: Had to handle URL-encoded author names and keywords
   - Used `urllib.parse.unquote()` to decode special characters in API paths (when searching papers by author's name)

4. **SK Prefix and Sorting**: DynamoDB string-based sorting caused issues
   - **Problem**: Date strings like "2009-04-29" sorted before "PAPERID" in descending order
   - **Solution**: Queried in ascending order and reversed results in application layer
   - Alternative would be using all date-prefixed SKs with different prefixes

5. **Filtering Limitations**: Cannot use FilterExpression on primary key attributes
   - **Problem**: Needed to filter category items from denormalized items
   - **Solution**: Implemented application-layer filtering by checking SK prefix patterns

6. **Deployment Script Issues**: 
   - Had to ensure both `query_papers.py` and `api_server.py` were uploaded
   - Fixed deployment script to use `--port` argument correctly

## Testing

**Local Testing**:
```bash
# Load data
python load_data.py data/papers.json arxiv-papers --region us-east-1

# Query tests
python query_papers.py recent cs.LG --limit 5
python query_papers.py author "Thomas G. Dietterich"
python query_papers.py get 0904.4608v2
python query_papers.py daterange cs.LG 2009-01-01 2009-12-31
python query_papers.py keyword learning --limit 5
```

**EC2 Testing**:
```bash
# Deploy
./deploy.sh ee547-ec2-key.pem 107.21.168.50

# Test API
curl "http://107.21.168.50:8080/papers/recent?category=cs.LG&limit=5"
curl "http://107.21.168.50:8080/papers/author/Thomas%20G.%20Dietterich"
curl "http://107.21.168.50:8080/papers/0904.4608v2"
curl "http://107.21.168.50:8080/papers/search?category=cs.LG&start=2009-01-01&end=2009-12-31"
curl "http://107.21.168.50:8080/papers/keyword/learning?limit=5"
```

## Key Learnings

1. **Denormalization is expensive**: 13.9x storage cost but necessary for read performance
2. **Schema design is critical**: Must know all access patterns upfront
3. **DynamoDB is powerful but limiting**: Excellent for specific patterns, poor for ad-hoc queries
4. **Application logic compensates**: Filtering and sorting often done in code, not database
5. **IAM roles simplify deployment**: Better than managing AWS credentials manually
6. **Query optimization requires pagination**: Must paginate through large result sets efficiently

## Conclusion

DynamoDB excels for high-scale, low-latency reads with predictable patterns. However, the trade-offs in query flexibility, storage costs, and data model constraints require careful consideration. For this use case with well-defined access patterns, DynamoDB provides excellent performance despite the storage overhead.
