#!/usr/bin/env bash
# Sends the training rounds through Mubit one after another, retries failed rows, writes the
# corrections to-do list, then waits for the 00:00 UTC training reset and sends the reserve round.
# Only the synthetic training rounds are listed; eval files are never sent from here.
#
# Run from evalkit/ with the laptop plugged in:  caffeinate -is ./autosend.sh
# The key is read from MUBIT_API_KEY or asked for once (hidden input). Log: runs/autosend.log

set -u
cd "$(dirname "$0")"

NOW_ROUNDS="team_train corrections r2_fresh"
AFTER_RESET_ROUNDS="r3_reserve"
RESET_AT="${RESET_AT:-2026-10-25T00:05:00Z}"   # 01:05 BST, five minutes after the daily reset
MODEL="${MODEL:-gpt-6-luna}"
PASSES=3
LOG=runs/autosend.log
mkdir -p runs

# One cheap request checks the key before any round is sent; Mubit answers 401 to a wrong key.
key_ok() {
  [[ "${MUBIT_API_KEY:-}" == mbt_* ]] || return 1
  [ "$(printf 'Authorization: Bearer %s' "$MUBIT_API_KEY" | curl -s -o /dev/null -w '%{http_code}' -H @- \
    https://api.mubit.ai/openai/v1/models)" != 401 ]
}
tries=0
until key_ok; do
  [ "$tries" -ge 3 ] && { echo "No working key after 3 tries. Nothing was sent."; exit 1; }
  [ -n "${MUBIT_API_KEY:-}" ] && echo "Mubit rejected that key. Copy the whole key again, or make a new one under Mubit keys."
  read -rsp "Paste the Mubit key (hidden, mbt_...): " MUBIT_API_KEY
  echo
  MUBIT_API_KEY="$(printf %s "$MUBIT_API_KEY" | tr -d '[:space:]')"
  export MUBIT_API_KEY
  tries=$((tries + 1))
done
echo "Key accepted."

say() { echo "$(date -u +%H:%M) UTC  $*" | tee -a "$LOG"; }

left_to_send() {
  uv run python -m evalkit.send_batch --chunks "../../data/rounds/$1.jsonl" --out "runs/$1.jsonl" --model "$MODEL" \
    | sed -n 's/.*already done, \([0-9]*\) to send.*/\1/p'
}

# Sends one round, then resends only the failed rows. Returns 1 when a pass makes no progress
# (credit gone or the gateway refusing), so the queue stops instead of burning calls.
send_round() {
  local r=$1 left before
  left=$(left_to_send "$r")
  for pass in $(seq 1 $PASSES); do
    [ "$left" = 0 ] && { say "$r: all sent"; return 0; }
    say "$r: pass $pass, $left to send"
    uv run python -m evalkit.send_batch --chunks "../../data/rounds/$r.jsonl" --out "runs/$r.jsonl" \
      --model "$MODEL" --live 2>&1 | tee -a "$LOG"
    before=$left
    left=$(left_to_send "$r")
    if [ "$left" = "$before" ]; then
      say "$r: no progress in pass $pass ($left left). Stopping. Check Billing and Requests in the console."
      return 1
    fi
    [ "$left" != 0 ] && sleep 60
  done
  [ "$left" = 0 ] && { say "$r: all sent"; return 0; }
  say "$r: $left rows still failing after $PASSES passes, moving on"
}

say "start: $NOW_ROUNDS now, $AFTER_RESET_ROUNDS after $RESET_AT, model $MODEL"
for r in $NOW_ROUNDS; do
  send_round "$r" || exit 1
  if [ "$r" = corrections ]; then
    uv run python -m evalkit.mistakes --gold ../../data/rounds/corrections.jsonl --results runs/corrections.jsonl \
      --out runs/corrections_todo.md --top 40 >> "$LOG" 2>&1
    say "corrections to-do written: training/evalkit/runs/corrections_todo.md (fix these in the console)"
  fi
done

wait_s=$(( $(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$RESET_AT" +%s) - $(date -u +%s) ))
if [ "$wait_s" -gt 0 ]; then
  say "waiting $(( wait_s / 3600 ))h $(( wait_s % 3600 / 60 ))m for the training reset"
  sleep "$wait_s"
fi
for r in $AFTER_RESET_ROUNDS; do
  send_round "$r" || exit 1
done
say "done: every round sent"
