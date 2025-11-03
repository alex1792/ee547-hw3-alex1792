# EE547 Homework 3

- **Name**: Yu Hung Kung

- **USCID**: 3431428440

- **EMAIL**: yuhungku@usc.edu

## Problem 1
**Quick Start**
```bash
chmod +x *.sh

# build
./build.sh

# run
./run.sh

# test
./test.sh
```


## Problem 2
**Quick Start**
**Prerequisites**:
```bash
# Configure AWS credentials (one-time setup)
aws configure
# Enter: Access Key ID, Secret Access Key, Region (e.g., us-east-1), Output format (json)
```

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