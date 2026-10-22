# Kagaz Testing Strategy

## 1. Purpose

This document defines the testing strategy for Kagaz, an AI-powered document workflow automation system. It explains the testing levels, the backend components that require testing, the approach for unit and integration testing, acceptance testing against user stories, and the process for recording test results.

The purpose of testing is to verify that Kagaz processes documents correctly, handles invalid inputs and failures safely, and provides the expected functionality to users.

This document describes the testing approach. A test described here must not be considered executed or passed until its result has been recorded from an actual test run.

## 2. Scope

Testing covers the backend functionality involved in document processing and the related application behaviour.

The main areas are:

- Document upload and input validation.
- Document metadata handling and persistence.
- Text extraction from supported documents.
- Document classification and classification-result validation.
- API health checks and error responses.
- Integration between the relevant document-processing stages.
- Acceptance testing against the project's documented user stories.

Frontend, database, external AI-service, and deployment testing should be included when the corresponding functionality is implemented and available in the test environment.

## 3. Testing Levels

### 3.1 Unit Testing

**Purpose:** Verify individual functions and small components independently.

Unit tests should cover document validation, metadata handling, extraction logic, classification-response parsing, and other backend logic.

The tests should include:

- Valid inputs and expected outputs.
- Empty, missing, malformed, or unsupported inputs.
- Boundary conditions, such as upload-size limits.
- Exceptions and error-handling paths.
- Invalid classification categories, confidence values, or responses.

External services, such as AI APIs, should be mocked when testing local logic so that unit tests remain predictable and do not require live API calls.

### 3.2 Integration Testing

**Purpose:** Verify that multiple components work correctly together.

Integration tests should focus on the document-processing workflow:

**Upload → Validation → Text Extraction → Classification → Metadata/Persistence**

The exact stages and order must follow the implementation currently present in the repository.

Integration tests should verify that:

- A valid document can move through the supported processing stages.
- Extracted text and classification results are passed to the appropriate components.
- Document metadata is handled correctly.
- Invalid uploads produce appropriate errors.
- Failures in one stage do not produce misleading successful results.
- API responses and persisted data are consistent with the expected behaviour.

Use test files, temporary storage, test database resources, or mocked external services as appropriate. Tests must not depend on production data or accidentally modify production resources.

### 3.3 Acceptance Testing

**Purpose:** Check whether Kagaz satisfies the requirements described in its user stories.

Acceptance tests should be derived from `docs/user-stories.md` and the relevant functional requirements.

For each selected user story:

1. Identify the user-visible behaviour and acceptance criteria.
2. Define the test preconditions and input data.
3. Specify the action performed by the user or API client.
4. Define the expected result.
5. Execute the test in the available environment.
6. Record the actual result and mark the test as passed, failed, blocked, or not run.

Acceptance testing should include successful document processing as well as relevant failure scenarios, such as invalid files and unsupported document formats.

A user story should not be marked as verified merely because a related unit test passes.

## 4. Backend Components and Testing Approach

The repository contains backend test areas for the following components. The implementation and test filenames should be checked against the current repository before changes are made.

| Component | What should be tested |
|---|---|
| Document upload | Valid uploads, missing files, invalid inputs, and upload responses |
| Upload validation and size limits | Unsupported files, oversized uploads, and boundary conditions |
| Text extraction | Successful extraction, multiple-page documents, whitespace handling, missing files, and unreadable documents |
| Classification | Valid classification results, invalid categories or confidence values, empty input, missing API configuration, and service failures |
| Document metadata | Required metadata, valid values, missing fields, and invalid values |
| Health endpoint | Expected response from the health-check endpoint |
| Document-processing workflow | Interaction between upload, extraction, classification, and metadata/persistence where implemented |

## 5. Unit-Testing Approach

Unit tests should be small, independent, repeatable, and easy to understand.

The project uses Python for the backend and has tests written in the pytest style. Use the repository's existing test conventions and dependencies rather than introducing a second testing framework unnecessarily.

The unit-testing approach should follow these principles:

- **Arrange:** Prepare the input, test data, and any required mocks.
- **Act:** Call the function or component being tested.
- **Assert:** Check the output, state change, or expected exception.
- Keep each test focused on one main behaviour.
- Use descriptive test names.
- Mock external network requests and AI services when the test is intended to verify local logic.
- Check both successful and unsuccessful cases.
- Ensure tests do not rely on execution order or live production resources.

Existing tests should be extended where appropriate instead of creating duplicate tests for the same behaviour.

## 6. Integration-Testing Approach

Integration tests should verify the interaction between connected backend components.

The principal workflow to validate is:

1. Submit a document through the upload endpoint.
2. Validate the file and its supported format and size.
3. Extract text from the document.
4. Classify the document using the available classification implementation.
5. Handle metadata and persistence as implemented.
6. Verify the API response and relevant resulting data.

### Important scenarios

| Scenario | Expected behaviour |
|---|---|
| Valid supported document | The implemented processing stages complete successfully |
| Missing upload | The API returns the expected validation error |
| Unsupported document | The request is rejected or handled according to the documented API behaviour |
| Oversized document | The upload-size limit is enforced |
| Unreadable document | The extraction failure is handled without reporting false success |
| Classification service failure | The error is handled without returning an invalid classification as successful |
| Invalid classification response | The response is rejected or handled according to the implementation's validation rules |
| Metadata or persistence failure | The failure is handled consistently, without misleading success |

These are scenarios to verify, not claims that every case is already implemented or has passed.

Where practical, integration tests should use temporary resources and mock external AI services. Tests involving real database or service integrations should run only when the necessary test configuration is available.

## 7. Acceptance Testing Against User Stories

Acceptance tests should be traceable to the requirements in `docs/user-stories.md` and the relevant functional requirements.

The following table gives an initial mapping. It should be updated with the exact user-story IDs and acceptance criteria found in the repository.

| User-facing capability | Acceptance-test focus |
|---|---|
| Upload a document | A supported document is accepted, and invalid uploads are handled correctly |
| Extract document information | Relevant text is extracted from supported documents, including multi-page documents where supported |
| Classify a document | The classification result follows the implemented category and response-validation rules |
| Handle processing errors | Invalid inputs and processing failures produce appropriate error responses |
| Access document metadata | Metadata is returned or stored correctly according to the implemented functionality |

Only mark a capability as verified after the corresponding test has actually been executed and its result recorded.

## 8. Test Environment and Execution

Tests should run in the project's configured Python environment with the dependencies specified by the repository.

Before execution:

1. Read the repository's setup instructions and dependency files.
2. Activate the project's virtual environment if one is used.
3. Install the documented development and test dependencies.
4. Configure required environment variables using the project's documented approach.
5. Ensure that tests use test resources rather than production resources.

From the repository root, the following is a possible pytest command if the test directory is `backend/tests/` and the project configuration supports running it from the root:

```bash
python -m pytest backend/tests/ -v
```

If the repository requires a different working directory, configuration, or command, use the verified project-specific command instead.

Do not place API keys, passwords, database credentials, or other secrets in the test document, test files, commits, or screenshots.

## 9. Test Results and Evidence

Test results must reflect the actual execution of the test suite.

For each test run, record:

- Date and time of execution.
- Branch or commit tested.
- Command used.
- Test scope.
- Total tests, passed tests, failed tests, and skipped tests, where reported.
- Failure details and relevant error messages.
- Environment limitations or external-service dependencies.
- Links to test logs, reports, screenshots, or other evidence, when available.

Use the following table to record results:

| Test run | Command or test scope | Passed | Failed | Skipped | Status / evidence |
|---|---|---:|---:|---:|---|
| To be recorded | To be recorded | — | — | — | Not run / evidence pending |

Update this table after running the tests. Do not enter assumed numbers or mark tests as passed without evidence.

A failed test should be investigated and documented. If a test cannot run because a dependency, environment variable, database, or external service is unavailable, record it as blocked or not run as appropriate.

## 10. Completion Criteria

The testing strategy is considered documented when:

- The purpose of unit, integration, and acceptance testing is explained.
- The key backend components and processing stages are identified.
- The unit-testing approach covers normal inputs, invalid inputs, and failure handling.
- Integration testing covers the implemented document-processing workflow.
- Acceptance testing is mapped to the project's actual user stories and requirements.
- The environment, test execution, and evidence-reporting process are described.
- Documented file paths, commands, and component names have been checked against the repository.
- Actual test results are recorded only when tests have been executed.

This document defines the testing strategy; implementation of missing tests and resolution of existing failures should be tracked separately when they fall outside the scope of the testing-strategy issue.
