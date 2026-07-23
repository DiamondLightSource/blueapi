#!/bin/bash
export PATH=$PATH:/opt/keycloak/bin

# --- Config ---
export KC_CLI_PASSWORD="admin"
SERVER="http://localhost:8080"
GENERAL_TEMPLATE="/tmp/config/mappers-template.json"
BEAMLINE_SERVICE_TEMPLATE="/tmp/config/service-account-beamline.json"
USER_SERVICE_TEMPLATE="/tmp/config/service-account-user.json"
REALM="master"

# Wait for Keycloak
sleep 5
until kcadm.sh config credentials --server $SERVER --realm $REALM --user admin; do sleep 3; done

# Cleanup logic
for type in "Allowed Protocol Mapper Types" "Allowed Client Scopes"; do
    for id in $(kcadm.sh get components -q name="$type" --fields id --format csv --noquotes); do
        kcadm.sh delete components/$id
    done
done


USERS=("alice:alice" "bob:bob")

for entry in "${USERS[@]}"; do
    # Split the string into username and password
    username="${entry%%:*}"
    password="${entry##*:}"
    # Create the user
    kcadm.sh create users -r "$REALM" -s username="$username" -s enabled=true
    # Set the password
    kcadm.sh set-password -r "$REALM" --username "$username" --new-password "$password"
    echo "User '$username' created successfully."
done

kcreg.sh config credentials --server $SERVER --realm $REALM --user admin

# --- Client Creation Function ---
# Args: client_id, audience, type, fedid, extra_flags
create_client() {
    local client_id=$1
    local aud=$2
    local type=$3
    local fedid=$4
    shift 4 # The rest are Keycloak attributes (-s key=value)

    if kcreg.sh get "$client_id" >/dev/null 2>&1; then
        echo ">> Skipping $client_id (exists)"
        return
    fi

    echo ">> Creating $client_id..."
    local tmpfile=$(mktemp)

    if [[ "$type" == "BEAMLINE_SERVICE_ACCOUNT" ]]; then
        cp  $BEAMLINE_SERVICE_TEMPLATE "$tmpfile"
    elif [[ "$type" == "USER_SERVICE_ACCOUNT" ]]; then
        sed "s/__AUDIENCE__/$aud/g; s/__CLAIM_VALUE__/$fedid/g" "$USER_SERVICE_TEMPLATE" > "$tmpfile"
    else
        # Use sed to replace placeholders in the JSON template
        sed "s/__AUDIENCE__/$aud/g;" "$GENERAL_TEMPLATE" > "$tmpfile"
    fi

    kcreg.sh create -x -s clientId="$client_id" -f "$tmpfile" "$@"
    rm "$tmpfile"
}

# --- Create Clients ---

# ixx CLI
create_client "ixx-cli-blueapi" "ixx-blueapi" "" "" \
    -s standardFlowEnabled=false -s publicClient=true -s 'redirectUris=["/*"]' \
    -s 'attributes={"frontchannel.logout.session.required":"true","oauth2.device.authorization.grant.enabled":"true","use.refresh.tokens":"true","backchannel.logout.session.required":"true"}'

# ixx BlueAPI
create_client "ixx-blueapi" "ixx-blueapi" "" "" \
    -s standardFlowEnabled=true -s secret="blueapi-secret" -s rootUrl="http://localhost:4180" \
    -s 'redirectUris=["http://localhost:4180/*"]' \
    -s 'attributes={"frontchannel.logout.session.required":"true","use.refresh.tokens":"true"}'

# Tiled
create_client "tiled" "tiled" "" "" \
    -s standardFlowEnabled=true -s secret="tiled-secret" -s rootUrl="http://localhost:4181" \
    -s 'redirectUris=["http://localhost:4181/*"]'

# Tiled CLI
create_client "tiled-cli" "tiled" "" ""\
    -s standardFlowEnabled=false -s publicClient=true -s 'redirectUris=["/*"]' \
    -s 'attributes={"frontchannel.logout.session.required":"true","oauth2.device.authorization.grant.enabled":"true","use.refresh.tokens":"true","backchannel.logout.session.required":"true"}'

# Service account tiled-writer
create_client "tiled-writer" "" "BEAMLINE_SERVICE_ACCOUNT" "" \
    -s secret="secret" -s standardFlowEnabled=false -s serviceAccountsEnabled=true -s 'redirectUris=["/*"]'

# System Test admin
create_client "system-test-blueapi-admin" "ixx-blueapi" "USER_SERVICE_ACCOUNT" "admin" \
    -s secret="secret" -s standardFlowEnabled=false -s serviceAccountsEnabled=true -s 'redirectUris=["/*"]'

# System Test alice
create_client "system-test-blueapi-alice" "ixx-blueapi" "USER_SERVICE_ACCOUNT" "alice"\
    -s secret="secret" -s standardFlowEnabled=false -s serviceAccountsEnabled=true -s 'redirectUris=["/*"]'

# System Test bob
create_client "system-test-blueapi-bob" "ixx-blueapi" "USER_SERVICE_ACCOUNT" "bob"\
    -s secret="secret" -s standardFlowEnabled=false -s serviceAccountsEnabled=true -s 'redirectUris=["/*"]'
