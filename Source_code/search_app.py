from flask import Flask, request, render_template
from elasticsearch import Elasticsearch
import math
import re

ELASTIC_PASSWORD = "wHUouaZQN4PjcL04Keq8"

es = Elasticsearch("https://localhost:9200", http_auth=("elastic", ELASTIC_PASSWORD), verify_certs=False)
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.template_filter('highlight')
def highlight_filter(s, keyword):
    return re.sub(re.escape(keyword), '<strong class="highlight">' + keyword + '</strong>', s, flags=re.IGNORECASE)

@app.route('/search')
def search():
    page_size = 10
    keyword = request.args.get('keyword')
    author_filter = request.args.get('author')
    created_filter = request.args.get('created')
    filter_type = request.args.get('filter_type')  # New filter parameter

    if request.args.get('page'):
        page_no = int(request.args.get('page'))
    else:
        page_no = 1
    
    # Check if the keyword has multiple words
    if " " in keyword:
        # Multiple word query
        search_terms = keyword.split(" ")
        body = {
            'size': page_size,
            'from': page_size * (page_no - 1),
            'query': {
                'bool': {
                    'must': [{'match': {'description': term}} for term in search_terms]
                }
            },
            'sort': [
                {
                    '_score': {
                        'order': 'desc'  # Sort by relevance score in descending order
                    }
                },
                {
                    'created': {
                        'order': 'desc'  # Secondary sort by created date in descending order
                    }
                }
            ]
        }
    # match all terms
    elif keyword == "":
        body = {
            'size': page_size,
            'from': page_size * (page_no - 1),
            'query': {'match_all': {}},  # Match all documents
            'sort': [
                {
                    'created': {
                        'order': 'desc'  # Sort by created date in descending order
                    }
                }
            ]
        }
    
    else:
        # One word query or partial match
        body = {
            'size': page_size,
            'from': page_size * (page_no - 1),
            'query': {
                'multi_match': {
                    'query': keyword,
                    'fields': ['name', 'description'],
                    'fuzziness': 'AUTO'  # Enable partial match
                }
            },
            'sort': [
                {
                    '_score': {
                        'order': 'desc'  # Sort by relevance score in descending order
                    }
                }
            ]
        }

    # Apply author filter if provided
    if author_filter:
        body['query']['bool']['must'].append({'match': {'author': author_filter}})

    # Apply created filter if provided
    if created_filter:
        body['query']['bool']['must'].append({'match': {'created': created_filter}})

    # Apply filter based on the selected type
    if filter_type and filter_type != 'all':
        body['query']['bool']['must'].append({'match': {'author': filter_type}})
        # Adjust this based on your actual filter types
    
    # Implement ranking logic based on our criteria
    # The existing sorting logic with a custom scoring function
    body['sort'] = [
        {
            '_score': {
                'order': 'desc'  # Sort by relevance score in descending order
            }
        },
        {
            'created': {
                'order': 'desc'  # Secondary sort by created date in descending order
            }
        }
    ]

    # For more advanced scoring, we can experiment with function_score query
    # Adjust the weight as needed based on our priorities
    # body['query'] = {
    #     'function_score': {
    #         'query': body['query'],
    #         'functions': [
    #             {
    #                 'filter': {'terms': {'tags': ['Living', 'Horoscope']}},
    #                 'weight': 2  # Boost the score for articles with tags 'Living' or 'Horoscope'
    #             }
    #         ],
    #         'score_mode': 'sum',
    #         'boost_mode': 'multiply'
    #     }
    # }

    # Enable highlighting
    body['highlight'] = {
        'pre_tags': ['<strong class="highlight">'],
        'post_tags': ['</strong>'],
        'fields': {
            'name': {},
            'description': {}
        }
    }

    res = es.search(index='articles', body=body)
    hits = [
        {
            'name': highlight_field(doc, 'name', filter_type),
            'description': highlight_field(doc, 'description', filter_type),
            'created': doc['_source']['created'],
            'author': doc['_source']['author'],
            'picture_src': doc['_source']['picture_src']
        }
        for doc in res['hits']['hits']
    ]
    page_total = math.ceil(res['hits']['total']['value'] / page_size)

    if not request.args.get('page'):
        # Display all results by setting page_no to 1 and page_total to the calculated total pages
        page_no = 1
        page_total = math.ceil(res['hits']['total']['value'] / page_size)
    
        return render_template('search.html', keyword=keyword, hits=hits, page_no=page_no, page_total=page_total)

    page_no = int(request.args.get('page'))
    return render_template('search.html', keyword=keyword, hits=hits, page_no=page_no, page_total=page_total)

def highlight_field(doc, field, filter_type):
    highlighted_field = doc.get('highlight', {}).get(field, [doc['_source'][field]])[0]

    # Check the filter type and apply highlighting accordingly
    if filter_type == 'author' and field == 'author':
        return '<strong class="highlight">' + highlighted_field + '</strong>'
    elif filter_type == 'created' and field == 'created':
        return '<strong class="highlight">' + highlighted_field + '</strong>'
    else:
        return highlighted_field
