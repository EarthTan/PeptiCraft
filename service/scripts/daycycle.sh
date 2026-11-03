#!/bin/sh
# Keep the folding batch inside the hours this machine is allowed to work.
#
# It lives in a shared room, so it runs between eight in the morning and eleven at night and
# is completely idle outside that window. Stopping the containers is what makes it quiet: the
# GPU drops from about 100 W to a few, and the fans follow. The machine keeps its ordinary
# power profile, because switching profiles needs an authorisation that a scheduled job
# cannot obtain.
#
# Run from cron every ten minutes rather than twice a day. A laptop suspends, wakes, reboots
# and misses timers; an idempotent check that asks "should it be running now?" recovers from
# all of those without needing to know which one happened.

START_HOUR=8
STOP_HOUR=23
SERVICE=pepticraft-fold
RUNNER=pepticraft-runner

hour=$(date +%H)
hour=${hour#0}
[ -z "$hour" ] && hour=0

running() {
    docker ps --format '{{.Names}}' | grep -qx "$1"
}

if [ "$hour" -ge "$START_HOUR" ] && [ "$hour" -lt "$STOP_HOUR" ]; then
    if ! running "$RUNNER"; then
        running "$SERVICE" || docker start "$SERVICE" >/dev/null 2>&1
        # The service takes about a minute to load three gigabytes of weights, and the runner
        # fails immediately if it asks for a prediction before that finishes.
        for _ in $(seq 1 30); do
            curl -sf -m 2 http://127.0.0.1:8204/health >/dev/null 2>&1 && break
            sleep 4
        done
        docker start "$RUNNER" >/dev/null 2>&1
    fi
else
    running "$RUNNER" && docker stop "$RUNNER" >/dev/null 2>&1
    running "$SERVICE" && docker stop "$SERVICE" >/dev/null 2>&1
fi

exit 0
