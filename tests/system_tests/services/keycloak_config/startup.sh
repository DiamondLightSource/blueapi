#!/bin/bash
export PATH=$PATH:/opt/keycloak/bin

# --- Config ---
export KC_CLI_PASSWORD="admin"
SERVER="http://localhost:8080"
TEMPLATE="/tmp/config/mappers-template.json"

# Wait for Keycloak
sleep 30
until kcadm.sh config credentials --server $SERVER --realm master --user admin; do sleep 1; done

# Cleanup logic
for type in "Allowed Protocol Mapper Types" "Allowed Client Scopes"; do
    for id in $(kcadm.sh get components -q name="$type" --fields id --format csv --noquotes); do
        kcadm.sh delete components/$id
    done
done

kcreg.sh config credentials --server $SERVER --realm master --user admin

# --- Client Creation Function ---
# Args: client_id, audience, extra_flags
create_client() {
    local client_id=$1
    local aud=$2
    shift 2 # The rest are Keycloak attributes (-s key=value)

    if kcreg.sh get "$client_id" >/dev/null 2>&1; then
        echo ">> Skipping $client_id (exists)"
        return
    fi

    echo ">> Creating $client_id..."
    local tmpfile=$(mktemp)

    if [[ "$client_id" == "tiled-writer" ]]; then
        cp /tmp/config/service-account.json "$tmpfile"
    else
        # Use sed to replace placeholders in the JSON template
        sed "s/__AUDIENCE__/$aud/g; s/__CLAIM_VALUE__/alice/g" "$TEMPLATE" > "$tmpfile"
    fi

    kcreg.sh create -x -s clientId="$client_id" -f "$tmpfile" "$@"
    rm "$tmpfile"
}

# --- Create Clients ---

# System Test
create_client "system-test-blueapi" "ixx-blueapi" \
    -s secret="secret" -s standardFlowEnabled=false -s serviceAccountsEnabled=true -s 'redirectUris=["/*"]'

# ixx CLI
create_client "ixx-cli-blueapi" "ixx-blueapi" \
    -s standardFlowEnabled=false -s publicClient=true -s 'redirectUris=["/*"]' \
    -s 'attributes={"frontchannel.logout.session.required":"true","oauth2.device.authorization.grant.enabled":"true","use.refresh.tokens":"true","backchannel.logout.session.required":"true"}'

# ixx BlueAPI
create_client "ixx-blueapi" "ixx-blueapi" \
    -s standardFlowEnabled=true -s secret="blueapi-secret" -s rootUrl="http://localhost:4180" \
    -s 'redirectUris=["http://localhost:4180/*"]' \
    -s 'attributes={"frontchannel.logout.session.required":"true","use.refresh.tokens":"true"}'

# Tiled
create_client "tiled" "tiled" \
    -s standardFlowEnabled=true -s secret="tiled-secret" -s rootUrl="http://localhost:4181" \
    -s 'redirectUris=["http://localhost:4181/*"]'

# Tiled CLI
create_client "tiled-cli" "tiled" \
    -s standardFlowEnabled=false -s publicClient=true -s 'redirectUris=["/*"]' \
    -s 'attributes={"frontchannel.logout.session.required":"true","oauth2.device.authorization.grant.enabled":"true","use.refresh.tokens":"true","backchannel.logout.session.required":"true"}'

# Service account tiled-writer
create_client "tiled-writer" "" \
    -s secret="secret" -s standardFlowEnabled=false -s serviceAccountsEnabled=true -s 'redirectUris=["/*"]'
