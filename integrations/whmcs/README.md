# WHMCS ↔ DeployUnit integratie

WHMCS verkoopt en factureert; DeployUnit levert het product. Deze module maakt bij een bestelling automatisch een DeployUnit-account aan (gebruiker + workspace, precies zoals een normale signup, inclusief welkomstmail en wachtwoord-instellink) en geeft de klant vanuit de WHMCS-clientarea één knop: **Open DeployUnit** (SSO, geen tweede login).

## Architectuur

```
WHMCS (my.servunit.com)                 DeployUnit backend
┌──────────────────────┐   X-Internal-Key   ┌──────────────────────────┐
│ module deployunit    │ ─────────────────▶ │ /api/internal/provision  │
│  CreateAccount       │                    │ /api/internal/plan       │
│  ChangePackage       │                    │ /api/internal/suspend    │
│  Suspend/Unsuspend   │                    │ /api/internal/unsuspend  │
│  Terminate           │                    │ /api/internal/terminate  │
│  ClientArea + SSO    │                    │ /api/internal/status     │
└──────────────────────┘                    │ /api/internal/sso (+consume) │
                                            └──────────────────────────┘
```

- Auth: header `X-Internal-Key` moet gelijk zijn aan env `INTERNAL_API_KEY` op de DeployUnit-backend. Zonder die env-var is de interne API volledig uitgeschakeld.
- Accounts die via WHMCS binnenkomen krijgen `billing_managed_by: "whmcs"` en `whmcs_service_id`; planwijzigingen raken **nooit** Mollie.
- Suspend zet `users.is_active = false` (nu ook afgedwongen in `get_current_user`) én stopt alle draaiende apps. Unsuspend herstart ze.
- Terminate ruimt alle workspaces/apps/databases/subdomeinen van de gebruiker op (zelfde cascade als workspace force-delete) en deactiveert het account.
- SSO: `POST /api/internal/sso` geeft een eenmalige URL (120 s geldig); de browser van de klant consumeert die op `/api/internal/sso/consume`, krijgt de normale sessiecookies en landt in `/app` — zelfde mechanisme als de GitHub OAuth-callback.

## Installatie

### 1. DeployUnit-backend

Zet een sterke sleutel in de backend-env en herstart:

```
INTERNAL_API_KEY=<64+ tekens random>
```

Let op: buiten `DEPLOYUNIT_ENV=production` worden Coolify/Cloudflare/MailerSend-writes ge-env-guard (suspend/terminate raken dan alleen de database, en er gaan geen mails uit).

### 2. WHMCS

1. Kopieer `integrations/whmcs/deployunit/` naar `<whmcs>/modules/servers/deployunit/`.
2. System Settings → Servers → Add New Server: Name `DeployUnit`, Hostname `deployunit.com`, Module **DeployUnit**, Access Hash = de `INTERNAL_API_KEY`, Secure aan. Test Connection moet groen zijn. Maak een servergroep en koppel de server.
3. Maak per DeployUnit-plan een product (bijv. groep "DeployUnit" met Starter/Pro/Agency): Module Settings → Module Name **DeployUnit**, servergroep kiezen, opslaan, daarna in de dropdown **Plan** het juiste plan kiezen (live geladen uit de API). Auto-setup op *payment*.
4. Prijzen instellen; klaar. Geen custom fields of configurable options nodig — de klant hoeft niets in te vullen, het domein/de apps regelt hij daarna zelf in DeployUnit.

## Gedrag per WHMCS-event

| WHMCS | DeployUnit |
|---|---|
| Order betaald (CreateAccount) | User aangemaakt (of gekoppeld op e-mail), workspace bootstrap, plan gezet, credits gevuld, welkomst- + wachtwoordmail |
| Upgrade/downgrade | `users.plan` + workspace-mirror bijgewerkt |
| Suspend | Account geblokkeerd + apps gestopt |
| Unsuspend | Account actief + apps herstart |
| Terminate | Alle workspaces/resources opgeruimd, account gedeactiveerd (user blijft bestaan voor historie) |
| "Open DeployUnit"-knop / SSO | Eenmalige loginlink, direct ingelogd in het dashboard |

Idempotentie: provision en terminate zijn veilig opnieuw uit te voeren; een tweede provision voor dezelfde service koppelt aan het bestaande account.
