#!/usr/bin/env bash
# The harness variables below are consumed by the sourced shared runner, so
# ShellCheck's unused-variable warning does not apply here.
# shellcheck disable=SC2034
set -euo pipefail

PROVIDER_SLUG=qwen
PROVIDER_LABEL=Qwen
MODEL=qwen4-max
BACKEND=token-plan-openai
EFFORT=high
RUNNER_NAME=delegation-qwen
API_KEY_ENV=QWEN_TOKEN_PLAN_API_KEY
API_KEY_VALUE=sk-sp-test
EXPECT_THINKING=false

# These variables are consumed by the sourced shared runner harness.
# shellcheck disable=SC2034
# shellcheck source=tests/lib/chat-completions-runner.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/chat-completions-runner.sh"

# A pre-existing personal model/effort pin must survive the new runner default.
rm -f "$TMP/results/success.out" "$TMP/results/success.out.metrics.json" "$TMP/results/success.out.error.json"
FAKE_PROVIDER_MODEL=qwen3.8-max DELEGATION_REQUESTED_MODEL=qwen3.8-max \
  run_case success 0 --effort xhigh
json "$TMP/results/success.request.json" '.model == "qwen3.8-max" and .reasoning_effort == "xhigh"'

# Read-only model discovery distinguishes access errors from a missing exact ID.
cat >"$TMP/bin/curl" <<'DISCOVERY'
#!/usr/bin/env bash
case "${FAKE_QWEN_DISCOVERY:?}" in
  unauthorized) exit 22 ;;
  malformed) printf '{"error":{"message":"unauthorized"}}' ;;
  missing) printf '{"data":[]}' ;;
  prefix) printf '{"data":[{"id":"qwen4-max-preview"}]}' ;;
  exact) printf '{"data":[{"id":"qwen4-max"}]}' ;;
esac
DISCOVERY
chmod +x "$TMP/bin/curl"
for entry in unauthorized:unknown malformed:unknown missing:not-yet-available prefix:not-yet-available exact:available; do
  mode="${entry%%:*}"; expected="${entry#*:}"
  PATH="$TMP/bin:$PATH" FAKE_QWEN_DISCOVERY="$mode" \
    "$RUNNER" check --json >"$TMP/check-$mode.json"
  actual="$(jq -r '.next_snapshot.availability' "$TMP/check-$mode.json")"
  [ "$actual" = "$expected" ] || fail "discovery $mode: got $actual, expected $expected"
done
printf 'Qwen exact-ID discovery, access failures and legacy pin preservation passed\n'
