#!/usr/bin/env bash
set -euo pipefail

image=${1:?Pass the locally built image tag}
work=$(mktemp -d)
data="$work/data"
container=''

cleanup() {
    local status=$?
    if [[ -n "$container" ]]; then
        if (( status != 0 )); then
            docker logs "$container" || true
        fi
        docker rm -f "$container" >/dev/null || true
    fi
    rm -rf "$work"
}
trap cleanup EXIT

run() {
    docker run --user "$(id -u):$(id -g)" --volume "$data:/data" "$@"
}

fetch() {
    curl --silent --show-error --fail --max-time 5 "$@"
}

start() {
    container=$(run --detach --publish 127.0.0.1::8080 "$image")
    base_url="http://$(docker port "$container" 8080/tcp)"
    fetch --retry 15 --retry-connrefused --retry-delay 1 --location "$base_url/" > "$work/front.html"
    grep -Fq 'System and Help Page Package installation' "$work/front.html"
}

mkdir "$data"
run --rm "$image" py3moin-init
start

logo=$(sed -n 's/.*src="\([^"]*\/common\/moinmoin.png\)".*/\1/p' "$work/front.html")
test -n "$logo"
fetch "$base_url$logo" --output "$work/logo.png"
cmp "$work/logo.png" MoinMoin/web/static/htdocs/common/moinmoin.png

# Permit editing in this isolated wiki with a loopback-only port.
docker rm -f "$container" >/dev/null
container=''
printf '\nConfig.acl_rights_default = "All:read,write"\n' >> "$data/wikiconfig.py"
start

page=DockerSmokePage
body='Saved by the Docker smoke test.'
form=$(fetch --cookie-jar "$work/cookies" "$base_url/$page?action=edit&editor=text")
ticket=$(sed -n 's/.*name="ticket" value="\([^"]*\)".*/\1/p' <<< "$form")
test -n "$ticket"
fetch --cookie "$work/cookies" --data-urlencode 'action=edit' --data-urlencode 'editor=text' \
    --data-urlencode 'rev=0' --data-urlencode "ticket=$ticket" --data-urlencode "savetext=$body" \
    --data-urlencode 'button_save=Save Changes' "$base_url/$page" > "$work/saved.html"
grep -Fq "$body" "$work/saved.html"
printf '%s\r\n' "$body" | cmp - "$data/data/pages/$page/revisions/00000001"

docker rm -f "$container" >/dev/null
container=''
cp "$data/wikiconfig.py" "$work/wikiconfig.py"
if output=$(run --rm "$image" py3moin-init 2>&1); then
    echo 'Initialization unexpectedly succeeded on an existing wiki' >&2
    exit 1
fi
grep -F 'directory is not empty' <<< "$output"
cmp "$work/wikiconfig.py" "$data/wikiconfig.py"

start
fetch "$base_url/$page" > "$work/reloaded.html"
grep -Fq "$body" "$work/reloaded.html"
echo 'Docker wiki initialization, page and static asset serving, and persistence passed'
