## 1. Establish the Claude Code Compatibility Contract

- [x] 1.1 Run the existing unit, context, and non-live integration suites on the task branch and record the clean baseline before changing runtime code
- [x] 1.2 On a machine with an authenticated Claude subscription, run a source-free compatibility spike covering `claude --version`, print mode, safe mode, disabled built-in and MCP tools, disabled slash commands, no session persistence, standard-input prompting, JSON output, and JSON-Schema structured output
- [x] 1.3 Record the minimum supported Claude Code version and exact schema-valid output envelope in `design.md` and add sanitized fixture data containing no account, credential, prompt, diff, or raw diagnostic content
- [x] 1.4 Add a failing compatibility test that rejects versions or structured-output envelopes outside the recorded contract before any production adapter implementation begins

## 2. Add Backend-Discriminated JSON Configuration

- [x] 2.1 Add failing configuration unit tests proving that missing `backend` and explicit `openai_compatible` preserve the current required fields and loaded values
- [x] 2.2 Add failing configuration unit tests for a valid keyless `claude_code` shape, missing or invalid model, prompt, and request limit, unsupported backends, inline-secret rejection, and backend-specific API-field handling
- [x] 2.3 Add failing context tests proving every invalid backend configuration fails before repository synchronization, diff generation, Claude execution, OpenAI requests, and PDF replacement
- [x] 2.4 Implement immutable backend-specific configuration types and exhaustive JSON validation with the legacy OpenAI-compatible default
- [x] 2.5 Update committed example and integration AI JSON files to name their backend explicitly while retaining at least one legacy-no-backend compatibility fixture
- [x] 2.6 Run the configuration unit and context tests and resolve all failures before starting the process adapter

## 3. Implement the Restricted Claude Code Client Test-First

- [x] 3.1 Add failing `ClaudeCodeClient` unit tests for fixed executable resolution, one successful version probe per client, missing executable, version timeout, nonzero version status, and empty version output
- [x] 3.2 Add failing unit tests that assert the exact argument-vector restrictions, `shell=False`, a temporary empty working directory, source-free arguments, source-bearing standard input, and cleanup after success or failure
- [x] 3.3 Add failing unit tests proving that every `summarize` and `reduce` call creates a distinct non-persistent process and that no session, response, prompt history, or module state crosses calls
- [x] 3.4 Add failing unit tests for schema-valid summary extraction and rejection of process timeout, nonzero status, malformed JSON, missing structured output, additional fields, non-string summary, and empty summary
- [x] 3.5 Add failing unit tests proving error messages omit standard-input payloads, raw stdout and stderr, environment values, authorization data, and expected-error tracebacks
- [x] 3.6 Add failing unit tests for immutable provenance containing only `claude_code`, the detected version, and requested model
- [x] 3.7 Implement the injected process-runner boundary and `ClaudeCodeClient` with fixed flags, standard-input payloads, fresh processes, bounded timeouts, safe temporary working-directory cleanup, and no credential access
- [x] 3.8 Implement strict structured-output parsing, stable `AISummarizationError` mapping, and secret-free provenance needed to pass the client unit suite
- [x] 3.9 Run the complete summarization unit suite and confirm the existing OpenAI-compatible client tests still pass

## 4. Select Backends and Carry Provenance Through the Workflow

- [x] 4.1 Add failing unit tests for exhaustive configured-client construction, preserving explicit `SummaryClient` injection and never constructing the unselected backend
- [x] 4.2 Add failing bounded-summarization tests for an immutable outcome containing ordered module summaries and execution provenance without changing chunking, request bounds, sequential reductions, or module isolation
- [x] 4.3 Add failing context tests proving `claude_code` is selected only for qualifying diffs, the OpenAI-compatible path remains unchanged, and the no-qualifying path executes neither backend nor any version probe
- [x] 4.4 Add failing context tests covering multiple modules and reduction levels, distinct process identities per request, exact request order, carried Claude provenance, and absence of cross-module payloads
- [x] 4.5 Implement the minimal backend factory, summarization outcome, and workflow changes needed to select the configured client and carry provenance without provider-specific introspection
- [x] 4.6 Preserve concise CLI handling for missing Claude, authentication, capacity, timeout, process, and output errors and prove that no final PDF replaces an existing destination after such failures
- [x] 4.7 Run the complete unit and context suites and resolve every regression before repository-facing integration work

## 5. Exercise the Real Subprocess Boundary and Linux Workflow

- [ ] 5.1 Add a deterministic fake `claude` executable harness that records only version, argument names, payload hashes and sizes, process identity, and working-directory facts and returns the supported schema-valid envelope
- [ ] 5.2 Add context tests using the real subprocess runner and fake executable to prove standard-input transport, inert shell metacharacters, restricted flags, temporary-directory cleanup, and one fresh operating-system process per request
- [ ] 5.3 Add context tests for fake executable timeout, nonzero exit, malformed result, login-style failure, and usage-limit-style failure, verifying sanitized errors, diff cleanup, and preservation of an existing PDF
- [ ] 5.4 Add a committed JSON integration configuration selecting `claude_code` for the separately managed public `git@github.com:torvalds/linux.git` fixture, with all generated paths redirected to framework-managed temporary locations
- [ ] 5.5 Add and run a non-live Linux integration test proving exact author/module filtering, bounded initial and reduction calls, request and process isolation, secret-free provenance, PDF generation, diff cleanup, and unchanged fixture refs, HEAD, index, worktree, and files
- [ ] 5.6 Add an explicit opt-in live Claude Code Linux integration that skips unless the executable, supported version, operator login, and opt-in flag are present and that stores no prompt, diff, credential, account identity, or raw process output

## 6. Reconcile Templates, Draft Provenance, Packaging, and Documentation

- [ ] 6.1 Update README requirements, configuration examples, invocation guidance, supported Claude Code version, authentication ownership, failure recovery, usage-limit behavior, and the warning that keyless Claude Code still transmits approved source content to the configured remote provider
- [ ] 6.2 Update packaged and repository AI configuration templates after configuration onboarding is available, with tests proving a Claude Code template contains no endpoint, key-variable name, key, OAuth token, or credential path
- [ ] 6.3 Reconcile onboarding validation and inspection after that prerequisite merges so both backend shapes receive stable diagnostics and inspection performs no version probe, login check, or inference request
- [ ] 6.4 Reconcile the release-governance lifecycle after that prerequisite merges so draft artifacts persist backend, requested model, and detected Claude Code version, bind them into draft integrity, and reject credentials or environment values
- [ ] 6.5 Add or update packaging smoke tests proving the installed wheel can load both backend configurations without a Claude SDK dependency and requires the external executable only when active Claude Code drafting begins

## 7. Complete Verification

- [ ] 7.1 Run the complete unit suite and resolve every failure
- [ ] 7.2 Run the complete context suite and resolve every failure
- [ ] 7.3 Run the complete non-live integration suite against the public Linux fixture and treat only a documented missing-fixture skip as acceptable
- [ ] 7.4 Run the opt-in live Claude Code integration when the supported executable, explicit flag, and operator login are available, otherwise record the intentional skip without weakening mandatory coverage
- [ ] 7.5 Build the source distribution and wheel, install the wheel in a clean environment, and run the packaged configuration and CLI smoke tests
- [ ] 7.6 Run `openspec validate add-claude-code-drafting-backend --type change --strict` and resolve every strict validation error before marking the change complete or committing implementation work
