#!/usr/bin/env python3
"""
API Server for ArXiv Papers DynamoDB Backend.
Uses Python standard library http.server only.
"""

import json
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import query_papers


class PapersAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for papers API endpoints."""
    
    def __init__(self, *args, **kwargs):
        # Get config from server
        self.table_name = kwargs.pop('table_name', 'arxiv-papers')
        self.region = kwargs.pop('region', 'us-east-1')
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        start_time = time.time() * 1000
        
        # Parse URL
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        # Log request
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] GET {path}", flush=True)
        
        try:
            # Route requests
            if path == '/papers/recent':
                response = self._handle_recent(query_params)
            elif path.startswith('/papers/author/'):
                author_name = unquote(path.split('/papers/author/')[-1])
                response = self._handle_author(author_name)
            elif path.startswith('/papers/search'):
                response = self._handle_search(query_params)
            elif path.startswith('/papers/keyword/'):
                keyword = unquote(path.split('/papers/keyword/')[-1])
                response = self._handle_keyword(keyword, query_params)
            elif path.startswith('/papers/'):
                arxiv_id = path.split('/papers/')[-1]
                response = self._handle_get_paper(arxiv_id)
            else:
                response = self._create_error_response(404, "Not Found")
            
            # Send response
            status_code = response['status_code']
            body = json.dumps(response['body'], indent=2, default=str)
            
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode('utf-8'))
            
            # Log execution time
            execution_time = int(time.time() * 1000 - start_time)
            print(f"  -> Status: {status_code}, Time: {execution_time}ms", flush=True)
            
        except Exception as e:
            print(f"  -> Error: {str(e)}", flush=True)
            response = self._create_error_response(500, "Internal Server Error")
            body = json.dumps(response['body'], indent=2, default=str)
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode('utf-8'))
    
    def _handle_recent(self, query_params):
        """Handle GET /papers/recent?category={category}&limit={limit}"""
        try:
            category = query_params.get('category', [None])[0]
            if not category:
                return self._create_error_response(400, "category parameter required")
            
            limit = int(query_params.get('limit', ['20'])[0])
            
            results = query_papers.query_recent_in_category(
                self.table_name, category, limit, self.region
            )
            
            # Format response
            papers = self._format_papers(results)
            body = {
                "category": category,
                "papers": papers,
                "count": len(papers)
            }
            return {"status_code": 200, "body": body}
            
        except ValueError:
            return self._create_error_response(400, "Invalid limit parameter")
        except Exception as e:
            print(f"Error in _handle_recent: {e}", flush=True)
            return self._create_error_response(500, "Internal Server Error")
    
    def _handle_author(self, author_name):
        """Handle GET /papers/author/{author_name}"""
        try:
            if not author_name:
                return self._create_error_response(400, "Author name required")
            
            results = query_papers.query_papers_by_author(
                self.table_name, author_name, self.region
            )
            
            # Format response
            papers = self._format_papers(results)
            body = {
                "author": author_name,
                "papers": papers,
                "count": len(papers)
            }
            
            if len(papers) == 0:
                return {"status_code": 404, "body": body}
            
            return {"status_code": 200, "body": body}
            
        except Exception as e:
            print(f"Error in _handle_author: {e}", flush=True)
            return self._create_error_response(500, "Internal Server Error")
    
    def _handle_get_paper(self, arxiv_id):
        """Handle GET /papers/{arxiv_id}"""
        try:
            if not arxiv_id:
                return self._create_error_response(400, "arXiv ID required")
            
            result = query_papers.get_paper_by_id(
                self.table_name, arxiv_id, self.region
            )
            
            if not result:
                return self._create_error_response(404, "Paper not found")
            
            # Format response
            paper = self._format_paper(result)
            body = {"paper": paper}
            
            return {"status_code": 200, "body": body}
            
        except Exception as e:
            print(f"Error in _handle_get_paper: {e}", flush=True)
            return self._create_error_response(500, "Internal Server Error")
    
    def _handle_search(self, query_params):
        """Handle GET /papers/search?category={category}&start={date}&end={date}"""
        try:
            category = query_params.get('category', [None])[0]
            start = query_params.get('start', [None])[0]
            end = query_params.get('end', [None])[0]
            
            if not category or not start or not end:
                return self._create_error_response(
                    400, "category, start, and end parameters required"
                )
            
            results = query_papers.query_papers_in_date_range(
                self.table_name, category, start, end, self.region
            )
            
            # Format response
            papers = self._format_papers(results)
            body = {
                "category": category,
                "start": start,
                "end": end,
                "papers": papers,
                "count": len(papers)
            }
            
            return {"status_code": 200, "body": body}
            
        except Exception as e:
            print(f"Error in _handle_search: {e}", flush=True)
            return self._create_error_response(500, "Internal Server Error")
    
    def _handle_keyword(self, keyword, query_params):
        """Handle GET /papers/keyword/{keyword}?limit={limit}"""
        try:
            if not keyword:
                return self._create_error_response(400, "Keyword required")
            
            limit = int(query_params.get('limit', ['20'])[0])
            
            results = query_papers.query_papers_by_keyword(
                self.table_name, keyword, limit, self.region
            )
            
            # Format response
            papers = self._format_papers(results)
            body = {
                "keyword": keyword,
                "papers": papers,
                "count": len(papers)
            }
            
            return {"status_code": 200, "body": body}
            
        except ValueError:
            return self._create_error_response(400, "Invalid limit parameter")
        except Exception as e:
            print(f"Error in _handle_keyword: {e}", flush=True)
            return self._create_error_response(500, "Internal Server Error")
    
    def _format_papers(self, results):
        """Format a list of papers for API response."""
        return [self._format_paper(item) for item in results]
    
    def _format_paper(self, item):
        """Format a single paper item for API response."""
        return {
            "arxiv_id": item.get('arxiv_id', ''),
            "title": item.get('title', ''),
            "authors": item.get('authors', []),
            "published": item.get('published', ''),
            "updated": item.get('updated', ''),
            "categories": item.get('categories', []),
            "abstract": item.get('abstract', ''),
            "keywords": item.get('keywords', [])
        }
    
    def _create_error_response(self, status_code, message):
        """Create standardized error response."""
        return {
            "status_code": status_code,
            "body": {"error": message}
        }


class PapersAPIServer:
    """API Server for papers queries."""
    
    def __init__(self, port=8080, table_name='arxiv-papers', region='us-east-1'):
        self.port = port
        self.table_name = table_name
        self.region = region
        
        # Create handler factory with config
        def handler_factory(*args, **kwargs):
            kwargs['table_name'] = self.table_name
            kwargs['region'] = self.region
            return PapersAPIHandler(*args, **kwargs)
        
        self.server = HTTPServer(('0.0.0.0', port), handler_factory)
    
    def run(self):
        """Start the server."""
        print(f"Starting API Server on port {self.port}")
        print(f"Table: {self.table_name}, Region: {self.region}")
        print(f"Endpoints:")
        print(f"  GET /papers/recent?category={{category}}&limit={{limit}}")
        print(f"  GET /papers/author/{{author_name}}")
        print(f"  GET /papers/{{arxiv_id}}")
        print(f"  GET /papers/search?category={{category}}&start={{date}}&end={{date}}")
        print(f"  GET /papers/keyword/{{keyword}}?limit={{limit}}")
        print("Press Ctrl+C to stop the server")
        print("-" * 60)
        
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.server.shutdown()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Papers API Server using DynamoDB backend'
    )
    parser.add_argument(
        '--port', type=int, default=8080,
        help='Port number (default: 8080)'
    )
    parser.add_argument(
        '--table', type=str, default='arxiv-papers',
        help='DynamoDB table name (default: arxiv-papers)'
    )
    parser.add_argument(
        '--region', type=str, default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    
    args = parser.parse_args()
    
    # Create and run server
    server = PapersAPIServer(
        port=args.port,
        table_name=args.table,
        region=args.region
    )
    server.run()


if __name__ == '__main__':
    main()

