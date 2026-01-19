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


for client in "system-test-blueapi" "ixx-cli-blueapi" "ixx-blueapi" "tiled" "tiled-cli"; do
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
      -f $tmpfile
      ;;
      "ixx-cli-blueapi")
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
          },
          {
            "name": "ixx-blueapi",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "config": {
              "introspection.token.claim": "true",
              "access.token.claim": "true",
              "included.custom.audience": "ixx-blueapi"
            }
          }
        ]
      }'
      echo $protocolMappers > $tmpfile
      kcreg.sh create -x \
      -s clientId=$client \
      -s standardFlowEnabled=false \
      -s publicClient=true \
      -s 'redirectUris=["/*"]' \
      -s 'attributes={"frontchannel.logout.session.required":"true","oauth2.device.authorization.grant.enabled":"true","use.refresh.tokens":"true","backchannel.logout.session.required":"true"}' \
      -f $tmpfile
      ;;
      "ixx-blueapi")
      kcreg.sh create -x \
      -s clientId=$client \
      -s standardFlowEnabled=true \
      -s publicClient=false \
      -s secret="blueapi-secret" \
      -s rootUrl="http://localhost:4180" \
      -s adminUrl="http://localhost:4180" \
      -s baseUrl="http://localhost:4180" \
      -s 'redirectUris=["http://localhost:4180/*"]' \
      -s 'webOrigins=["http://localhost:4180/*"]' \
      -s 'attributes={"frontchannel.logout.session.required":"true","use.refresh.tokens":"true","standard.token.exchange.enabled": "true","standard.token.exchange.enableRefreshRequestedTokenType": "SAME_SESSION"}' \
      -f $tmpfile
      ;;
      "tiled")
      sed -i 's/blueapi/tiled/g' $tmpfile
      kcreg.sh create -x \
      -s clientId=$client \
      -s standardFlowEnabled=true \
      -s publicClient=false \
      -s secret="tiled-secret" \
      -s rootUrl="http://localhost:4181" \
      -s adminUrl="http://localhost:4181" \
      -s baseUrl="http://localhost:4181" \
      -s 'redirectUris=["http://localhost:4181/*"]' \
      -s 'webOrigins=["http://localhost:4181/*"]' \
      -s 'attributes={"frontchannel.logout.session.required":"true","use.refresh.tokens":"true"}' \
      -f $tmpfile
      ;;
      "tiled-cli")
      sed -i 's/blueapi/tiled/g' $tmpfile
      kcreg.sh create -x \
      -s clientId=$client \
      -s standardFlowEnabled=false \
      -s publicClient=true \
      -s 'redirectUris=["/*"]' \
      -s 'attributes={"frontchannel.logout.session.required":"true","oauth2.device.authorization.grant.enabled":"true","use.refresh.tokens":"true","backchannel.logout.session.required":"true"}' \
      -f $tmpfile
      ;;
      esac
      rm $tmpfile
  fi
done
