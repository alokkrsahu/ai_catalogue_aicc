# Django Milvus Search Package

A comprehensive, highly maintainable Milvus vector search integration for Django applications.

## Features

- **Comprehensive Algorithm Support**: Test and use 25+ Milvus algorithms including FLAT, IVF_FLAT, IVF_SQ8, IVF_PQ, HNSW, SCANN, and AUTOINDEX
- **Django Integration**: Native Django app with settings, views, URLs, and management commands
- **Thread-Safe Operations**: Built-in connection pooling and concurrent search capabilities
- **Performance Monitoring**: Built-in metrics collection and performance analysis
- **Algorithm Testing**: Comprehensive testing framework to find optimal algorithms for your use case
- **RESTful API**: Ready-to-use REST endpoints for search operations
- **Caching Support**: Optional Redis caching for improved performance
- **Error Handling**: Comprehensive exception handling with detailed error types
- **Type Safety**: Full type hints and dataclass-based models

## Installation

### 1. Install Dependencies

```bash
pip install pymilvus django
```

### 2. Add to Django Project

Copy the `django_milvus_search` package to your Django project or install as a package.

### 3. Add to INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    # ... your apps
    'django_milvus_search',
]
```

### 4. Configure Milvus Settings

```python
# settings.py
MILVUS_CONFIG = {
    'host': 'localhost',
    'port': '19530',
    'max_connections': 8,
    'timeout': 60.0,
    'user': None,  # Optional
    'password': None,  # Optional
    'secure': False,  # Set to True for TLS connections
}
```

### 5. Include URLs

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    # ... your URLs
    path('milvus/', include('django_milvus_search.urls')),
]
```

## Quick Start

### Basic Search Operation

```python
from django_milvus_search import MilvusSearchService
from django_milvus_search.models import SearchRequest, IndexType, MetricType

# Initialize service (uses Django settings)
service = MilvusSearchService()

# Create search request
request = SearchRequest(
    collection_name="my_collection",
    query_vectors=[[0.1, 0.2, 0.3, 0.4]],  # Your vector
    index_type=IndexType.HNSW,
    metric_type=MetricType.COSINE,
    limit=10
)

# Perform search
result = service.search(request)

# Access results
for hit in result.hits:
    print(f"ID: {hit['id']}, Score: {hit['score']}, Distance: {hit['distance']}")
```

### Algorithm Testing

```python
from django_milvus_search.utils import AlgorithmTester

# Initialize tester
tester = AlgorithmTester()

# Run comprehensive test
results = tester.run_comprehensive_test()

# View summary
summary = results["summary"]
print(f"Tested {summary['total_tests']} algorithms")
print(f"Success rate: {summary['success_rate']:.1f}%")
print(f"Fastest algorithm: {summary['fastest_algorithms'][0][0]}")
```

### Using Django Management Command

```bash
# Test all algorithms
python manage.py test_milvus_algorithms

# Test specific collections
python manage.py test_milvus_algorithms --collections collection1 collection2

# Save results to file
python manage.py test_milvus_algorithms --output results.json

# Use different Milvus instance
python manage.py test_milvus_algorithms --host 192.168.1.100 --port 19530
```

## API Endpoints

### Search Vectors
```http
POST /milvus/search/
Content-Type: application/json

{
    "collection_name": "my_collection",
    "query_vectors": [[0.1, 0.2, 0.3, 0.4]],
    "index_type": "HNSW",
    "metric_type": "COSINE",
    "search_params": {"ef": 64},
    "limit": 10,
    "output_fields": ["title", "content"]
}
```

### List Collections
```http
GET /milvus/collections/
```

### Get Collection Info
```http
GET /milvus/collections/?collection=my_collection
```

### Health Check
```http
GET /milvus/search/
```

### Run Algorithm Test
```http
POST /milvus/test/
Content-Type: application/json

{
    "collections": ["collection1", "collection2"],
    "max_workers": 5
}
```

## Advanced Usage

### Custom Connection Configuration

```python
from django_milvus_search.models import ConnectionConfig
from django_milvus_search.services import MilvusSearchService

config = ConnectionConfig(
    host="remote-milvus.example.com",
    port="19530",
    user="username",
    password="password",
    secure=True
)

service = MilvusSearchService(config=config)
```

### Batch Search Operations

```python
requests = [
    SearchRequest(collection_name="collection1", query_vectors=[[0.1, 0.2]]),
    SearchRequest(collection_name="collection2", query_vectors=[[0.3, 0.4]]),
]

results = service.batch_search(requests)
```

### Performance Monitoring

```python
# Get metrics
metrics = service.get_metrics()
print(f"Total searches: {metrics['total_searches']}")
print(f"Average search time: {metrics['average_search_time']:.4f}s")
print(f"Success rate: {metrics['success_rate']:.2%}")

# Reset metrics
service.reset_metrics()
```

### Custom Algorithm Testing

```python
from django_milvus_search.models import AlgorithmConfiguration, SearchParams

# Create custom configuration
config = AlgorithmConfiguration(
    name="CustomHNSW",
    index_type=IndexType.HNSW,
    metric_type=MetricType.L2,
    search_params=SearchParams(ef=128),
    description="HNSW with high precision"
)

# Test single algorithm
result = tester.test_single_algorithm(config, "my_collection", 768)
```

## Error Handling

The package provides comprehensive error handling with specific exception types:

```python
from django_milvus_search.exceptions import (
    MilvusConnectionError,
    MilvusSearchError,
    MilvusConfigurationError,
    MilvusCollectionError
)

try:
    result = service.search(request)
except MilvusConnectionError:
    # Handle connection issues
    pass
except MilvusSearchError as e:
    # Handle search-specific errors
    print(f"Search failed: {e.message}")
    print(f"Details: {e.details}")
except Exception as e:
    # Handle unexpected errors
    pass
```

## Configuration Options

### Django Settings

```python
# Complete configuration example
MILVUS_CONFIG = {
    'host': 'localhost',
    'port': '19530',
    'max_connections': 8,
    'timeout': 60.0,
    'user': 'milvus_user',
    'password': 'secure_password',
    'secure': True,  # Enable TLS
}

# Optional: Redis caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'milvus_search',
        'TIMEOUT': 300,
    }
}

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'milvus_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'milvus_search.log',
        },
    },
    'loggers': {
        'django_milvus_search': {
            'handlers': ['milvus_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Testing

Run the test suite:

```bash
# Run all tests
python manage.py test django_milvus_search

# Run specific test class
python manage.py test django_milvus_search.tests.TestModels

# Run with coverage
coverage run --source='.' manage.py test django_milvus_search
coverage report
```

## Performance Tips

1. **Use Connection Pooling**: The service automatically manages connections, but you can configure `max_connections` in settings.

2. **Choose Right Algorithm**: Use the algorithm tester to find the best performing algorithm for your data.

3. **Batch Operations**: Use `batch_search()` for multiple searches to improve throughput.

4. **Enable Caching**: Configure Redis caching for frequently accessed data.

5. **Monitor Performance**: Use the built-in metrics to track performance over time.

## Migration from Original Script

If you're migrating from the original `test_all_algorithms.py` script:

1. Replace direct imports with the package imports
2. Use `MilvusSearchService` instead of `ConcurrentSearchEngine`
3. Use `AlgorithmTester` for testing functionality
4. Configure connection through Django settings
5. Use the management command for testing

Example migration:

```python
# Old way
from search_engine import ConcurrentSearchEngine
from models import ConnectionConfig, SearchRequest

engine = ConcurrentSearchEngine(max_workers=10)
engine.add_milvus_instance("test", config)

# New way
from django_milvus_search import MilvusSearchService
from django_milvus_search.models import SearchRequest

service = MilvusSearchService(max_workers=10)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This package is released under the MIT License.

## Support

For issues and questions:
1. Check the test suite for examples
2. Review the comprehensive error handling
3. Use the built-in health check endpoint
4. Enable debug logging for troubleshooting
