# External integrations and their exact boundary

## Broker connections

Public visitors use **Live investing workspace → Indian markets → Connect Zerodha**. They sign in to InvestorsEYE, then follow the official broker login link. They do not supply developer keys or secrets.

The site operator configures `KITE_API_KEY` and `KITE_API_SECRET` in the hosting secret store. Obtain multi-user approval from Zerodha before setting `KITE_MULTI_USER_ENABLED=true`. A personal application key is not proof of public multi-user access. Zerodha's published guidance: https://kite.trade/forum/discussion/14684/multi-user-access-with-same-api-key

Register `https://investoreye.harkiratsingh.tech/v1/connections/kite/callback` in the application's developer settings. `PUBLIC_BASE_URL` must match the deployed HTTPS origin. Until configuration and approval are supplied, the public UI shows the connection as unavailable and keeps public crypto markets usable.

Each investor's returned token is encrypted in their own account record. The application secret stays in server configuration. Authorization state is expiring and single-use. **Verify connection** checks the broker profile. Quotes and charts use that investor's data access. **Refresh holdings and positions** retrieves a broker snapshot without touching the virtual wallet or importing user CSVs.

Historical chart entitlement is separate from a successful profile login. Reconnection, provider denial and throttling remain visible errors. Controlled tests establish isolation and state handling; actual broker acceptance requires a real approved application and investor login.

Upstox's separate developer-credential connection remains available as an earlier integration. It is not the new public Zerodha onboarding flow.

## Notification channels

Open **Notification channels**. Configure Telegram bot/chat, authenticated SMTP, or WhatsApp Business credentials. Save, send a verification code, enter the received code, then queue a test notification. No agent verification step sends messages to arbitrary recipients.

Channels are private and encrypted. Provider acceptance is `sent`, not `confirmed`. Signed WhatsApp receipts can set `confirmed`. Timeouts after potential acceptance become `uncertain` and require explicit retry to avoid duplicate messages. Connection failures before acceptance have bounded retries. Quiet hours are stored per channel.

WhatsApp needs a configured business number, template and recipient consent. Configure `WHATSAPP_APP_SECRET` and `WHATSAPP_WEBHOOK_VERIFY_TOKEN` to use `/v1/webhooks/whatsapp`. Real delivery remains unverified until a configured recipient confirms receipt.

## Account email

Set `AUTH_SMTP_HOST`, `AUTH_SMTP_PORT`, `AUTH_SMTP_USER`, `AUTH_SMTP_PASSWORD`, and `AUTH_SMTP_FROM` securely in the deployment environment. Account verification and recovery tokens expire after 20 minutes and can be used once. Password recovery revokes all sessions. No email delivery is claimed when SMTP is absent.

## Private deployment

`compose.yaml` runs PostgreSQL, web, provider/notification worker and scheduled training. Data, models and runtime keys have named volumes. `compose.production.yaml` adds Caddy HTTPS and restricts the private team's source IP ranges. Set `APP_DOMAIN`, `ALLOWED_CLIENT_CIDRS`, `POSTGRES_PASSWORD`, `EYE_ENCRYPTION_KEY`, and `PUBLIC_BASE_URL` through the hosting environment. Back up the encryption key separately from the encrypted database backup.

The public release uses `compose.yaml` plus `compose.public.yaml`; its HTTPS proxy is `deploy/Caddyfile.public`. The IP-restricted team configuration remains separate in `compose.production.yaml`. No cloud deployment is claimed. The most recent `investors-eye` AWS identity check returned an expired session; renew that named session before provisioning. A final public domain is also required.


## Selected public domain

The selected address is `https://investoreye.harkiratsingh.tech`. Non-secret deployment values are saved in `deploy/domain.env`; apply them with the production secrets when launching Compose:

```bash
docker compose --env-file .env --env-file deploy/domain.env -f compose.yaml -f compose.public.yaml up -d --build
```

DNS inspection on 14 November 2026 returned authoritative nameservers `ns1.dns.host` through `ns4.dns.host`, with no A or CNAME answer for the selected subdomain. The registrar dashboard and DNS-hosting dashboard may differ. Once the deployment supplies a stable address, add only the `investoreye` record there, using the exact A or CNAME target provided by the chosen host. No hosting target has been allocated yet. DNS has not been modified.
