# Authenticate to BlueAPI

## Introduction
BlueAPI provides a secure and efficient way to interact with its services. This guide walks you through the steps to log in and log out using BlueAPI with OpenID Connect (OIDC) authentication.

## Configuration

:::{seealso}
[Configure the Application](./configure-app.md)
:::

Here is an example configuration for authenticating to p46-blueapi:

```yaml
api:
  host: "p46-blueapi.diamond.ac.uk"
  port: 443
  protocol: "https"

auth_token_path: "~/.cache/blueapi_cache"  # Optional: Custom path to store the token
```

- **auth_token_path**: (Optional) Specify where to save the token. If omitted, the default is `~/.cache/blueapi_cache` or `$XDG_CACHE_HOME/blueapi_cache` if `XDG_CACHE_HOME` is set.

---

## Log In

1. Execute the login command:

   ```bash
   $ blueapi -c config.yaml login
   ```

2. **Authenticate**:
   - Follow the prompts from your OIDC provider to log in.
   - Provide your credentials and complete any additional verification steps required by the provider.

3. **Success Message**:
   Upon successful authentication, you see the following message:

   ```
   Logged in and cached new token
   ```

---

## Log Out

To log out and securely remove the cached access token, follow these steps:

1. Execute the logout command:

   ```bash
   $ blueapi logout
   ```

2. **Logout Process**:
   - This command uses the OIDC flow to log you out from the OIDC provider.
   - It also deletes the cached token from the specified `auth_token_path`.

3. **Success Message**:
   If the token is successfully removed or if it does not exist, you see the message:

   ```
   Logged out
   ```
