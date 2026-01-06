#!/bin/bash
export PATH=$PATH:/opt/keycloak/bin

sleep 30
while ! kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin; do
    sleep 1
done

allowed_protocol_mappers=$(kcadm.sh get components -q name="Allowed Protocol Mapper Types" --fields id --format csv --noquotes)
allowed_client_scopes=$(kcadm.sh get components -q name="Allowed Client Scopes" --fields id --format csv --noquotes)
for i in $allowed_protocol_mappers $allowed_client_scopes;do
  kcadm.sh delete components/$i
done

kcreg.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin

protocolMappers='{
  "protocolMappers": [
    {
      "name": "fedid",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-hardcoded-claim-mapper",
      "config": {
        "introspection.token.claim": "true",
        "claim.value": "alice",
        "userinfo.token.claim": "true",
        "id.token.claim": "true",
        "access.token.claim": "true",
        "claim.name": "fedid",
        "jsonType.label": "String"
      }
    },
    {
      "name": "blueapi",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-audience-mapper",
      "config": {
        "introspection.token.claim": "true",
        "access.token.claim": "true",
        "included.custom.audience": "blueapi"
      }
    }
  ]
}'


for client in "system-test-blueapi" "ixx-cli-blueapi"; do
  if ! kcreg.sh get "$client" >/dev/null 2>&1; then
      tmpfile=$(mktemp)
      echo $protocolMappers > $tmpfile
      case $client in
      "system-test-blueapi")
      kcreg.sh create -x \
      -s clientId=$client \
      -s secret="secret" \
      -s standardFlowEnabled=false \
      -s serviceAccountsEnabled=true \
      -s 'redirectUris=["/*"]' \
      -s attributes='{"access.token.lifespan":"86400"}' \
      -f $tmpfile
      ;;
      "ixx-cli-blueapi")
      kcreg.sh create -x \
      -s clientId=$client \
      -s standardFlowEnabled=false \
      -s publicClient=true \
      -s 'redirectUris=["/*"]' \
      -s 'attributes={"access.token.lifespan":"86400","frontchannel.logout.session.required":"true","oauth2.device.authorization.grant.enabled":"true","use.refresh.tokens":"true","backchannel.logout.session.required":"true"}' \
      -f $tmpfile
      ;;
      esac
      rm $tmpfile
  fi
done
