#!/bin/bash
# Test scripts for Part C and Part D API

# Part C: Direct query tests
echo "=== Part C: Testing Direct Queries ==="
echo ""

echo "Test 1: Recent papers in category"
python query_papers.py recent cs.LG --limit 5 > test_query1_recent.json
echo "  Output: test_query1_recent.json"
echo ""

echo "Test 2: Papers by author"
python query_papers.py author "Thomas G. Dietterich" > test_query2_author.json
echo "  Output: test_query2_author.json"
echo ""

echo "Test 3: Get paper by ID"
python query_papers.py get 0904.4608v2 > test_query3_get.json
echo "  Output: test_query3_get.json"
echo ""

echo "Test 4: Papers in date range"
python query_papers.py daterange cs.LG 2009-01-01 2009-12-31 > test_query4_daterange.json
echo "  Output: test_query4_daterange.json"
echo ""

echo "Test 5: Papers by keyword"
python query_papers.py keyword learning --limit 5 > test_query5_keyword.json
echo "  Output: test_query5_keyword.json"
echo ""

# Part D: API Server tests (only if server is running)
if curl -s http://localhost:8080/papers/recent?category=cs.LG\&limit=1 > /dev/null 2>&1; then
    echo "=== Part D: Testing API Server ==="
    echo ""
    
    echo "Test 1: Recent papers (API)"
    curl -s "http://localhost:8080/papers/recent?category=cs.LG&limit=5" | python -m json.tool > test_api1_recent.json
    echo "  Output: test_api1_recent.json"
    echo ""
    
    echo "Test 2: Papers by author (API)"
    curl -s "http://localhost:8080/papers/author/Thomas%20G.%20Dietterich" | python -m json.tool > test_api2_author.json
    echo "  Output: test_api2_author.json"
    echo ""
    
    echo "Test 3: Get paper by ID (API)"
    curl -s "http://localhost:8080/papers/0904.4608v2" | python -m json.tool > test_api3_get.json
    echo "  Output: test_api3_get.json"
    echo ""
    
    echo "Test 4: Papers in date range (API)"
    curl -s "http://localhost:8080/papers/search?category=cs.LG&start=2009-01-01&end=2009-12-31" | python -m json.tool > test_api4_search.json
    echo "  Output: test_api4_search.json"
    echo ""
    
    echo "Test 5: Papers by keyword (API)"
    curl -s "http://localhost:8080/papers/keyword/learning?limit=5" | python -m json.tool > test_api5_keyword.json
    echo "  Output: test_api5_keyword.json"
    echo ""
else
    echo "API Server is not running. Start it with:"
    echo "  python api_server.py --port 8080"
    echo ""
fi

echo "=== All tests complete ==="

