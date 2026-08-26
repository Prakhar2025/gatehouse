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

## [2026-08-26] pack path assumed one filesystem shape and broke every lambda invocation
Symptom: every live webhook call 500ed at runtime composition with pack file not found: /var/packs/in/pack.yaml, while the suite stayed green.
Root cause: _default_pack_path derived the repo layout from __file__ parents and never considered that under Lambda the package sits at /var/task/gatehouse with packs/ as its sibling. The lookup landed on /var instead of /var/task.
Fix: candidate list covering repo root layout, lambda task-root sibling layout, and a future layer mount; first existing candidate wins, env override still absolute. Path tests now pin all three layouts so drift fails in CI.
Prevention: any path derived from __file__ must have a test per deployment filesystem shape, not just the developer machine.
Phase: channels layer

## [2026-08-26] dynamo binding store leaked raw botocore errors past the runtime contract
Symptom: live bind of an already-linked chat returned 500 with ConditionalCheckFailedException instead of the friendly already-linked refusal.
Root cause: the in-memory store raises AlreadyLinkedError on the failed uniqueness condition; the dynamo store let the raw ClientError escape. Two backends, two contracts.
Fix: the conditional link write translates ConditionalCheckFailedException into AlreadyLinkedError, matching the memory backend. Regression test drives a fake client that raises the real botocore error shape.
Prevention: every store method that can fail must document which contract exception escapes; backend parity belongs in tests, not hope.
Phase: channels layer

## [2026-08-26] telegram retry storm fed by non-200 answers on member errors
Symptom: an expired-code /start produced a 500, Telegram re-delivered the same update indefinitely (pending_update_count climbing), and the member saw silence instead of the expiry message.
Root cause: two defects stacked. The consume-side condition failure escaped as raw botocore error (backend parity gap, same class as the link-write bug), and the route answered 500 for what is a member-correctable condition, which Telegram treats as retry-forever.
Fix: consume_invite translates ConditionalCheckFailedException to InviteError like the memory backend, and the route answers 200 on loop failures with the error logged in full, so a bad update is dropped once and recorded, never retried into a storm.
Prevention: member-correctable conditions must map to member-facing answers, never transport failures; webhook contracts retry, so any non-200 must mean our infrastructure is broken, not the caller's input.
Phase: channels layer

## [2026-08-26] real bank SMS flagged because the issuer registry and URL extraction were too thin
Symptom: a genuine UCO Bank ATM alert was flagged DOMAIN_UNVERIFIED; the SBI scam with a bare domain (no scheme) was not hard-failed.
Root cause: the pack listed 7 issuers with partial domains, so ucoonline.bank.in was unknown; the URL regex required a scheme, so bare scam domains like sbi-verify.top were invisible to the issuer-claim rule; and amount strings like rs.83675.45.for were extracted as phantom domains.
Fix: issuer registry grown to 17 Indian banks and payment entities with real official domains; URL extraction now catches bare domains and filters numeric phantom hosts; classifier counts bare-domain presence as a URL signal.
Prevention: detection data is a product surface, not a config afterthought; every real-miss soak message must end in the failure taxonomy and a pack or rule change.
Phase: channels layer

## [2026-08-26] issuer verification could only fail, never clear, so genuine bank traffic stayed flagged
Symptom: even with ucoonline.bank.in in the registry, the UCO alert stayed SUSPICIOUS on TRIAGE_SCREEN because link presence alone bumps triage to SCREEN and nothing downstream could cancel it.
Root cause: the issuer rule had one polarity (FAIL on spoof) and no PASS polarity (verified on authentic), so no evidence could ever clear a link-driven flag. A fraud shield that cannot say verified is half a shield.
Fix: issuer claim adjudication now has both outcomes, PASS with weight 0.9 when links resolve inside the claimed issuer's domain, FAIL on spoof; the guardian gains an issuer-verified kill switch that returns SAFE with ISSUER_VERIFIED when every domain finding passes and the issuer claim passes.
Prevention: every rule must define both its positive and negative outcome; a check that can only add risk accumulates false positives without bound.
Phase: channels layer

## [2026-08-26] private schema class name broke every structured model call
Symptom: triage with the real Bedrock model raised tool-not-found in the agent loop and no-valid-tool-use at the model interface; spend stayed zero and the loop degraded to rules-only.
Root cause: strands registers the structured-output schema as a tool named after the CLASS. The class was _TriageModel with a leading underscore; Nova called the tool TriageModel, the names never matched, and both call paths failed on lookup.
Fix: schema classes are public (TriageModel); triage calls the model structured_output interface directly instead of the Agent loop, which also removes a needless agent round trip.
Prevention: any class registered as a bedrock tool via pydantic conversion must have a public name; add a live-model smoke test to CI-parity gates so this fails in seconds locally, not in production logs.
Phase: deployment

## [2026-08-26] chaos audit found dependency faults the pipeline would have crashed on
Symptom: writing the P4 chaos suite against the doc 03 failure matrix showed three rows with no real boundary: an exception in verify_signal or the graph store propagated straight out of investigate() as a 500, and a DynamoDedupeStore outage raised inside run_pipeline before any investigation started.
Root cause: only the triage stage had a try/except degradation path; verify, graph, dedupe, and bundle-write were trusted to be total even though every one of them crosses a network or data-dependency boundary. The failure matrix documented degraded behavior that no code implemented.
Fix: every dependency-backed stage now runs inside its own fault boundary with an explicit degradation: verify loss forces NEEDS_HUMAN with VERIFICATION_UNAVAILABLE instead of a quiet SAFE, graph loss produces the GRAPH_UNAVAILABLE finding, dedupe fails open with a warning, bundle writes were already contained. Triage breaker refusals stopped being silent: the reason code carries budget_refused and the guardian maps it to TRIAGE_BUDGET_REFUSED on the package. Member replies gained an honest NEEDS_HUMAN branch and NEEDS_HUMAN escalates to the guardian review queue so the promise in the reply text is true. A canary leak into any member-visible reply is now intercepted (CANARY_TRIP) before delivery instead of detected only after.
Prevention: the chaos suite (tests/test_chaos.py) runs every matrix row on every push; a new degraded-behavior claim in any doc must ship with its row test in the same commit.
Phase: deployment
