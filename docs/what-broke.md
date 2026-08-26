Fix: aliases list added to schema and India pack; verify matches name or alias.
Prevention: test_bank_name_with_foreign_link_fails covers the alias path.
Phase: agent layer

## [2026-08-25] lockfile carried dev-only AWS tooling into CI
Symptom: heavy universal lockfile churn around the channels-layer push; risk of ubuntu-only resolution failures from Windows/tooling extras.
Root cause: requirements-aws.txt (bedrock-agentcore-starter-toolkit, sam-cli transitives) was compiled into the single runtime lockfile; deploy tooling does not belong in app dependencies.
Fix: runtime lockfile regenerated from requirements.txt alone (universal, py3.12); AWS deploy tooling stays a local-only extra install, not a CI dependency. mangum added as a real runtime dep for the Lambda handler.
Prevention: CI installs only the runtime lockfile; deploy tooling documented in doc 09 setup, never compiled into app locks.
Phase: channels layer

## [2026-08-25] test fake for binding store did not match boto3 delete_item semantics
Symptom: test_lookup_and_unlink failed; unlink returned False for a binding that existed.
Root cause: test fake returned {"Attributes": {}} on delete; the real check `bool(resp.get("Attributes"))` treats an empty dict as no attributes, so the binding was treated as not deleted.
Fix: fake now returns the deleted item as Attributes, matching boto3 ReturnValues=ALL_OLD.
Prevention: the protocol-level `bool` check is the contract; fakes must mirror real return shapes for every method they implement.
Phase: channels layer

## [2026-08-25] quiet-hours test fixtures hand-computed epochs wrongly
Symptom: module-level sanity asserts failed on import; gmtime disagreed with the comment by 15 hours.
Root cause: UTC timestamps for fixture moments were computed by hand instead of derived from civil time.
Fix: fixtures built via calendar.timegm over an explicit aware datetime; sanity asserts now prove placement.
Prevention: never hand-compute epoch values in tests; always construct from civil time and assert the derived hour.
Phase: channels layer

## [2026-08-25] engagement turns_used counted the opener against the six-turn budget
Symptom: turn-limit test expected 6 budgeted turns, got 7.
Root cause: transcript counts every OUT line; doc 04 caps model turns, and the scripted opener (turn 0) is not a model turn.
Fix: turns_used counts OUT records with turn >= 1; opener excluded by definition at the single exit point.
Prevention: budget semantics belong next to the counter, documented where the number is produced, not only in the test.
Phase: channels layer

## [2026-08-25] callback expiry math treated timestamp 0.0 as missing
Symptom: expired-callback test got outcome applied instead of expired.
Root cause: case age used an or-chain over decided_at/created_at/now; a legitimate created_at of 0.0 is falsy and fell through to now, making every case brand new.
Fix: explicit None checks instead of truthiness when reading timestamps from stored records.
Prevention: epoch timestamps are never truthiness-checked; absence is None, zero is a point in time.
Phase: channels layer

## [2026-08-25] CI ran a newer ruff than local, missed UP017
Symptom: CI red on lint step with UP017 use-datetime-utc-alias; local green.
Root cause: local venv had an older ruff; requirements-lock.txt pins a newer one. Toolchain drift, not a code bug.
Fix: switched to the datetime.UTC import alias and synced local ruff to the lockfile version. Future drift: make rebase against the lockfile a precondition of "local green equals CI green."
Prevention: rebuild the venv from requirements-lock.txt when ruff and CI disagree.
Phase: channels layer

## [2026-08-25] gitleaks action failed because checkout was depth-1
Symptom: CI red on gitleaks step with "ambiguous revision", but the message also said zero leaks.
Root cause: actions/checkout defaults to fetch-depth 1, so the parent commit range the action wanted did not exist in the working tree.
Fix: checkout now uses fetch-depth 0, giving the action the full history it needs. Zero leaks confirmed, not a real finding.
Prevention: any tool that needs history (gitleaks, blame, bisect) needs fetch-depth 0 in the checkout step.
Phase: channels layer

## [2026-08-25] two-step dedupe reservation flagged every first message as duplicate
Symptom: caught in review before testing; the provisional-case-id reservation would have returned the just-recorded slot as a hit on the real call.
Root cause: reserving under a placeholder id and re-recording under the real id treats the second write as a repeat of the first.
Fix: reserve once under the real case id; the same call atomically answers hit-or-miss.
Prevention: idempotency reservations must be single-shot under the final identity, never staged through throwaway keys.
Phase: channels layer

## [2026-08-25] aware-datetime epoch fixtures drifted by the UTC offset again
Symptom: quiet-hours fixture sanity assert failed; 15:00 IST read back as 20:30.
Root cause: calendar.timegm over dt.timetuple() ignores the tzinfo offset; naive wall time was hashed as if UTC.
Fix: utctimetuple() for aware datetimes; sanity asserts prove the derived local hour.
Prevention: this ledger already had this rule; recurrence proves hand-built epochs stay dangerous. Builders must derive from civil time via utctimetuple only.
Phase: channels layer

## [2026-08-25] uv-managed venv has no pip module; Docker off on this host
Symptom: build script calling `.venv/Scripts/python.exe -m pip` failed; docker daemon not running for sam build containers.
Root cause: environment uses uv, not pip; container builds need Docker Desktop started.
Fix: layer assembly via `uv pip install --target --python-platform aarch64-unknown-linux-gnu --only-binary`, source zip via shutil.make_archive with Windows-native paths (pwd -W).
Prevention: packaging scripts target uv semantics on this host; no-Docker Lambda packaging documented in docs/deploy-lambda.md.
Phase: channels layer

## [2026-08-25] missing-guardian-chat test passed by day and failed by night
Symptom: test_missing_guardian_chat_raises went red on an evening run with DID NOT RAISE NotificationError.
Root cause: escalate() defaults to the real wall clock; inside quiet hours (22:00 to 07:00 local, IST offset) a DECISION card queues into the digest before the guardian-chat guard ever fires, so nothing raises.
Fix: injected the awake-hour fixture timestamp like every sibling test; the guard is now exercised regardless of when the suite runs.
Prevention: assertions about routing must pin the clock explicitly; wall-clock defaults make tests time-of-day dependent, same failure family as the epoch fixtures rule already in this ledger.
Phase: channels layer

## [2026-08-26] reserved DynamoDB keywords shipped a 500ing bind path past a green suite
Symptom: first live /start bind returned HTTP 500; local suite was fully green.
Root cause: consumed, expires_at, and taint are DynamoDB reserved keywords used as bare attribute names inside update and condition expressions. In-memory fakes accept any grammar, so only the live service rejected them.
Fix: all expressions now use ExpressionAttributeNames placeholders across binding, graph, and persistence stores. New conftest guard fails any test-recorded Dynamo call carrying a bare reserved word, so this defect class can no longer reach main.
Prevention: fakes must encode the real service's grammar rules or a contract test must; green-on-fake proves nothing about wire-format validation.
Phase: channels layer
