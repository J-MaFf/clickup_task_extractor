# Test Suite Documentation

This directory contains comprehensive unit tests for the ClickUp Task Extractor project.

## Overview

The test suite includes 120 tests covering all major modules and functionality:

- **test_mappers.py** (31 tests) - Utility helpers and data mapping
- **test_logger_config.py** (23 tests) - Logging configuration
- **test_ai_summary_success.py** (18 tests) - AI summary generation
- **test_api_client.py** (17 tests) - API client and error handling
- **test_auth.py** (16 tests) - Authentication and secret resolution
- **test_extractor_edge_flows.py** (15 tests) - Task extraction workflows

## Running Tests

### Run All Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Run Specific Test Module

```bash
python -m unittest tests.test_mappers
```

### Run Specific Test Class

```bash
python -m unittest tests.test_api_client.TestClickUpAPIClient
```

### Run Specific Test Method

```bash
python -m unittest tests.test_mappers.TestGetDateRange.test_this_week_with_enum
```

### Run with Verbose Output

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

## Test Coverage

### test_mappers.py

Tests for utility functions in `mappers.py`:

- **TestGetDateRange** (6 tests)
  - Tests date range calculation for ThisWeek, LastWeek filters
  - Tests enum and string input handling
  - Tests invalid filter fallback behavior

- **TestExtractImages** (10 tests)
  - Tests markdown image syntax extraction
  - Tests HTML img tag extraction
  - Tests direct URL patterns (jpg, png, gif, etc.)
  - Tests attachment patterns
  - Tests case-insensitive matching

- **TestLocationMapper** (8 tests)
  - Tests ID-based location mapping
  - Tests orderindex-based mapping
  - Tests name-based mapping
  - Tests fallback behaviors

- **TestGetYesNoInput** (7 tests)
  - Tests yes/no/y/n inputs
  - Tests keyboard interrupts and EOF handling
  - Tests default values on interrupt

### test_api_client.py

Tests for API client in `api_client.py`:

- **TestClickUpAPIClient** (14 tests)
  - Tests successful GET requests
  - Tests authentication errors (401)
  - Tests network errors (timeout, connection)
  - Tests invalid JSON responses
  - Tests various HTTP status codes (400, 404, 429, 500)
  - Tests error message formatting

- **TestAPIErrorExceptions** (3 tests)
  - Tests custom exception inheritance
  - Tests exception message preservation

### test_auth.py

Tests for authentication in `auth.py`:

- **TestLoadSecretWithFallback** (7 tests)
  - Tests successful SDK retrieval
  - Tests CLI fallback on SDK failure
  - Tests complete failure handling
  - Tests subprocess command construction

- **TestGetSecretFrom1Password** (5 tests)
  - Tests ImportError when SDK unavailable
  - Tests ValueError when service token missing
  - Tests successful secret retrieval
  - Tests exception wrapping with context

- **TestLoggingBehavior** (4 tests)
  - Tests logging at each fallback stage
  - Tests success and failure logging

### test_extractor_edge_flows.py

Tests for extraction workflows in `extractor.py`:

- **TestExportFile** (3 tests)
  - Tests directory creation
  - Tests existing directory handling
  - Tests custom encoding

- **TestGetExportFields** (2 tests)
  - Tests exclusion of private fields
  - Tests return type validation

- **TestInteractiveInclude** (3 tests)
  - Tests selecting all tasks
  - Tests selective task selection
  - Tests rejecting all tasks

- **TestMultiFormatExport** (4 tests)
  - Tests CSV export
  - Tests HTML export
  - Tests Both format (CSV + HTML)
  - Tests empty task list handling

- **TestErrorHandling** (3 tests)
  - Tests workspace not found
  - Tests authentication errors
  - Tests API errors

### test_ai_summary_success.py

Tests for AI summarization in `ai_summary.py`:

- **TestNormalizeFieldEntries** (3 tests)
  - Tests tuple sequence normalization
  - Tests mapping normalization
  - Tests string conversion

- **TestGetAISummaryFallback** (3 tests)
  - Tests empty field entries
  - Tests no API key fallback
  - Tests no GenAI SDK fallback

- **TestGetAISummarySuccess** (5 tests)
  - Tests successful summary generation
  - Tests period addition
  - Tests newline removal
  - Tests empty response handling

- **TestRateLimitingAndRetry** (4 tests)
  - Tests successful retry after rate limit
  - Tests all retries failing
  - Tests retry delay extraction
  - Tests non-rate-limit error handling

- **TestPromptConstruction** (3 tests)
  - Tests task name inclusion
  - Tests field label inclusion
  - Tests correct model usage

### test_logger_config.py

Tests for logging configuration in `logger_config.py`:

- **TestSetupLogging** (10 tests)
  - Tests logger instance creation
  - Tests log level setting
  - Tests handler clearing
  - Tests Rich handler usage
  - Tests file handler creation
  - Tests directory creation
  - Tests console output control

- **TestGetLogger** (4 tests)
  - Tests default logger retrieval
  - Tests custom name handling
  - Tests None parameter handling
  - Tests instance caching

- **TestRichHandlerConfiguration** (2 tests)
  - Tests Rich handler parameters
  - Tests console stdout usage

- **TestLogLevels** (5 tests)
  - Tests DEBUG, INFO, WARNING, ERROR, CRITICAL levels

## Test Design Principles

### Mocking

Tests use `unittest.mock` extensively to:
- Mock external dependencies (requests, 1Password SDK, Gemini API)
- Isolate units under test
- Control test conditions
- Avoid network calls and side effects

### Test Independence

Each test:
- Sets up its own fixtures
- Cleans up after itself
- Can run in any order
- Does not depend on other tests

### Temporary Files

Tests that write to disk use:
- `tempfile.TemporaryDirectory()` for automatic cleanup
- Context managers to ensure cleanup on exceptions

### Patching

Tests patch at appropriate levels:
- `@patch('module.function')` for function-level mocking
- `@patch.dict('os.environ')` for environment variables
- `@patch('module.Class')` for class-level mocking

## Contributing

When adding new functionality:

1. Write tests for the new code
2. Follow existing test patterns
3. Ensure tests are independent
4. Use descriptive test names
5. Add docstrings explaining what is tested
6. Run full test suite before committing

## Coverage Goals

Aim for high coverage of:
- ✅ Core business logic
- ✅ Error handling paths
- ✅ Edge cases and boundary conditions
- ✅ User interaction flows
- ✅ External API interactions

## Known Limitations

Some areas not fully covered:
- Integration tests with real ClickUp API
- End-to-end workflow tests
- Performance and load testing
- UI/CLI interaction testing (limited by Rich console mocking)

## Resources

- [Python unittest documentation](https://docs.python.org/3/library/unittest.html)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Testing best practices](https://docs.python-guide.org/writing/tests/)
