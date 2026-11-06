Test data for the central authorisation OPA (gitlab.diamond.ac.uk/auth-auth/authorisation).

Mounted over `/dummy_bundle` in the authorisation image, which loads it when no
`BUNDLER_BEARER_TOKEN` is set. Same shape as the real data bundle; see
`dummy_bundle/` in the authorisation repo.

- admin: super_admin
- alice: named on session cm12345-1 (adsim)
- bob:   named on session cm12345-2 (adsim)
