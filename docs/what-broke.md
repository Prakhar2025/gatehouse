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
