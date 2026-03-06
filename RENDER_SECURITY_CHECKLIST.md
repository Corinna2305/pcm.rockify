# Render Security Checklist

## 1. Repository and Access
- Keep repository private.
- Enable 2FA on GitHub account.
- Restrict write access to trusted collaborators.

## 2. Environment Variables (Render)
- Store secrets only in Render environment variables.
- Never hardcode secrets in `rockify.py`.
- Rotate secrets periodically and after suspected exposure.

## 3. Host and CORS
- Set `TRUSTED_HOSTS` to your real domains.
- Set `CORS_ALLOW_ORIGINS` to exact frontend origins (no wildcard in production).
- Verify preflight (`OPTIONS`) works only for allowed origins.

## 4. Authentication and Session
- Keep secure password policy enabled.
- Monitor repeated login failures.
- Revoke sessions on suspicious behavior.

## 5. Abuse Protection
- Keep per-IP rate limiting active on login/register/public search endpoints.
- Add upstream protections (Cloudflare/WAF) if traffic grows.
- Review logs for scraping or brute-force patterns.

## 6. Data and Storage
- Prefer managed Postgres over local SQLite for production durability.
- Ensure backups for critical data.
- Validate and sanitize uploaded file names and types.

## 7. Transport and Browser Security
- Enforce HTTPS on public app.
- Keep `https_only` stream filter for better browser compatibility.
- Add security headers (HSTS/CSP) when custom domain is stable.

## 8. Legal and Product Protection
- Add clear Terms of Use and Privacy Policy pages.
- Register domain and brand name early.
- Publish a license file that matches your intended rights policy.

## 9. Operational Practices
- Pin dependencies and update regularly.
- Monitor Render deploy logs after every release.
- Run smoke tests on `/docs`, `/world-radio`, `/api/world-radios`.
