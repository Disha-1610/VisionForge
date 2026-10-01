# Security

> This describes how access is controlled, and where the weak points are.
> Checked against the code in September 2026.

---

## Read this first

This section describes what is actually built, including the parts that are not built yet.

**Two things that are often assumed but are not true here:**

- **Evidence records are not permanent and cannot be assumed unchangeable.** Nothing enforces
  that, and deleting an inspection does delete its evidence.
- **Reports are not stamped with a SHA-256 hash to prove they were not altered.** **There is no
  hashing anywhere in the backend.** The module that would need it is not even imported.

Both are covered below and in [problems.md](../problems.md).

---

## Table of contents

1. [How login works](#1-how-login-works)
2. [The two roles](#2-the-two-roles)
3. [What each role can reach](#3-what-each-role-can-reach)
4. [Where the weak points are](#4-where-the-weak-points-are)
5. [What is not built](#5-what-is-not-built)
6. [Settings that change how secure it is](#6-settings-that-change-how-secure-it-is)
7. [What to fix first](#7-what-to-fix-first)

---

## 1. How login works

### Passwords

Passwords are hashed with **bcrypt** before being stored. bcrypt is designed to be slow on purpose,
which is what makes it a reasonable choice for passwords. The project uses the library default,
which is 12 rounds of hashing.

The real password is never stored, and never written to a log.

### Tokens

Two tokens are issued on login.

| Token | Lifetime | Purpose |
|---|---|---|
| Access token | **30 minutes** | Sent on every request |
| Refresh token | **7 days** | Exchanged for a new pair without asking the user to log in again |

Both are signed with **HS256**, a standard signing method. The signature uses a secret key from the
environment.

Inside each token there are four claims: the user ID, the role, an expiry, and whether it is an
access or a refresh token.

**One thing worth knowing:** the role inside the token is never actually used for decisions. Every
protected request looks the user up in the database and reads the current role from there. So
changing someone's role takes effect on their very next request, without waiting for their token to
expire. That is the safer arrangement.

### The secret key

The signing key comes from an environment variable called `JWT_SECRET_KEY`.

**The default value in the code is `change-me-in-production`.** If that is left in place, anyone
who has read the source can forge a valid token for any user. The example environment file says
`generate-a-random-secret-key-here`, which is a reminder and not a real secret.

## 2. The two roles

There are exactly two, and both values are lowercase on the wire.

| Role | What it is for |
|---|---|
| `operator` | The person doing the inspections. The everyday user |
| `admin` | The person who manages suppliers, reference images, and settings |

There is no third role. No auditor, no viewer, no superadmin.

## 3. What each role can reach

**Everyone who is logged in:**

- View inspections, including any inspection, not only their own
- View and download reports
- Approve an inspection
- Override an inspection
- Delete a report
- List and view reference images
- List and view suppliers
- See analytics, limited to their own inspections
- Ask the machine for its network address

**Admins only:**

- Create, edit, and delete suppliers
- Upload, create, and delete reference images
- See analytics across all operators

**Anyone, no login needed:**

- Register a new account
- Log in
- Refresh a token
- Read the health check
- Read the API documentation
- **Watch a live inspection through the progress stream**

**Three things stand out as wrong or inconsistent:**

1. **Registration lets you choose your own role.** Anyone can register as an admin. This is the most
   serious problem in the project.
2. **The live progress stream needs no login at all.** Anyone who knows an inspection ID can watch
   it and read its verdict.
3. **Any logged-in user can delete any report.** Every other delete in the project is admin-only.

Details in [problems.md](../problems.md).

**One more, less obvious:** there is no separation between organisations anywhere. Analytics filter
by vendor and location, and the summary limits an operator to their own inspections, but the
individual inspection, report, and evidence endpoints check only that someone is logged in. In a
single-company setup that is fine. In a multi-tenant setup it is a data leak.

## 4. Where the weak points are

### High: anyone can register as an admin

Already covered. The registration endpoint takes a `role` field and uses whatever is sent.

### High: the live stream has no authentication

`GET /api/v1/inspections/{id}/events` has no login check. It is the only data endpoint in the
project without one. Inspection IDs are random UUIDs, so this is not trivially guessable, but a
returned ID is enough, and the app hands them out in the interface.

### High: the signing key has a guessable default

`change-me-in-production` is a well-known placeholder. If it reaches production unchanged, tokens
can be forged.

### High: development passwords are committed

`admin@visionforge.ai` with `adminpassword123` and `operator@visionforge.ai` with
`operatorpassword123` are in the code as startup seed data. They are in the repository, in
`README.md`, and in this file. They must not survive into a real deployment.

### High: API keys are in the repository

`backend/.env` and `backend/.env.example` both contain real-looking cloud provider keys. See
[problems.md](../problems.md) issue 8.

### Medium: no rate limiting

Nothing stops a client sending unlimited requests. There is no rate limiter, no per-user limit, and
no per-IP limit. The two cloud providers do have their own limits, so a burst of inspections would
exhaust those, and the user would see failures rather than a clear "slow down" message.

### Medium: refresh tokens cannot be revoked

The server issues refresh tokens but keeps no record of them. A refresh token stays valid for its
full 7 days. If one is stolen, there is no way to invalidate it. The only remedy is to wait it out
or to change the signing key, which logs everyone out.

### Medium: the tunnel URL is written in plain text

`frontend/.env` holds the public tunnel address, and `frontend/.tunnel.url` holds it again. The
tunnel exposes the whole development server, not just the inspection page. It is not restricted to
authenticated operators.

### Medium: the tunnel runs the development server

The tunnel points at the Vite development server on port 5173. That is the right tool for a demo on
a factory floor with no internet. It is not a production deployment, and it should not be treated
as one.

### Low: uploads are checked by extension only

`backend/app/utils/file_utils.py` checks that the filename ends in an allowed extension, then
saves the file under a fresh random name. It does not look at the contents.

**There is no file content validation and no upload size limit.** `python-magic` is not installed
and not imported, and there is no size check anywhere in the upload path. A 15 MB per-image limit
does not exist.

There is good news here, though. The check is against a fixed list of image extensions, the file is
renamed to a generated UUID, and the stored name is built from that UUID rather than from anything
the user sent, which prevents an uploaded file from being used to write somewhere else.

### Low: two error response shapes

Errors from the project's own handler have `detail` as a string. Validation errors come back with
`detail` as a list of objects. Clients need to handle both. There is also a set of custom exception
classes that are registered but never raised.

### Low: the API documentation's login button does not work

It is configured for a form login, but the endpoint expects JSON. Cosmetic, and it does not affect
security.

## 5. What is not built

**Genuinely absent, not just weak:**

| Missing | Notes |
|---|---|
| File content validation | Extension check only. No magic byte validation |
| Upload size limit | None. No size check anywhere in the upload path |
| Rate limiting | Not present on any endpoint |
| Evidence immutability enforcement | No trigger or constraint. Deletes happen through the cascade from inspections |
| Report signing or hashing | No hashing in the backend at all |
| Rejecting wildcard origins in production | The allowed origins are a plain list, and the middleware takes whatever is in it. No `*` check |
| A health endpoint that reports component status | The only health check returns the service name and version |
| CSRF protection | Not present. Worth noting, since the access token is kept in local storage rather than a cookie, which is the usual reason CSRF matters less |
| Security headers | None are set. No strict transport security, no content type policy, no frame options |
| Audit log | No audit trail table exists |
| Input length limits on text fields | None, beyond what the database column widths impose |

**On the health endpoint:** the only health check returns the service name and version. It does not
report whether the database, the vector index, or the model loaded successfully. So a deployment
cannot tell a healthy service from one whose database connection failed.

## 6. Settings that change how secure it is

All of these come from `backend/.env`.

| Setting | Default | What it affects |
|---|---|---|
| `JWT_SECRET_KEY` | `change-me-in-production` | **Must be changed.** If not, tokens can be forged |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | How long a session lasts before a refresh |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | 7 | How long a user stays logged in |
| `JWT_ALGORITHM` | `HS256` | The signing method |
| `CORS_ORIGINS` | `http://localhost:5173`, `http://localhost:3000` | Which websites may call the API |
| `ENVIRONMENT` | `development` | Used to pick the database |
| `DEBUG` | `True` | **Should be `False` in production** |

**Two things to be careful with.**

`CORS_ORIGINS` is a list of full addresses including the port. `http://localhost:5173` and
`https://localhost:5173` are different as far as the browser is concerned, so switching to HTTPS
means changing this list too. And the middleware allows all methods and all headers, so this list is
the only thing restricting which sites can call the API.

`DEBUG` defaults to `True`. It should be `False` anywhere real.

**A note on what CORS is and is not doing here.** It stops other websites from calling this API from
a visitor's browser. It does not stop a direct request from anywhere on the network. The CORS
settings are not an access control.

## 7. What to fix first

In order:

1. **Stop registration accepting a role.** Ignore the field and always create operators. This is a
   few lines and it closes the most serious hole.
2. **Add a login check to the live stream.** One line, using the same dependency as every other
   endpoint.
3. **Require a role on report deletion.** It is already required everywhere else.
4. **Change the signing key and the seed passwords** before this goes anywhere public.
5. **Remove the API keys from the repository** and rotate them.
6. **Add a file size limit and content checking on uploads.** Even a simple size check would close
   an obvious gap.
7. **Add rate limiting** on the endpoints that call the cloud providers, so a burst returns a clear
   message instead of failing.
8. **Decide what evidence permanence means**, and enforce it with a database trigger if it matters.
9. **Add security headers** and turn `DEBUG` off.
10. **Build a real health endpoint** that reports whether the database, the vector index, and the
    model actually loaded.

The first three are small changes with a large effect. They are the ones worth doing before anything
else.

---

*Next: [DEPLOYMENT.md](DEPLOYMENT.md) for running the project, or
[problems.md](../problems.md) for the full list of problems.*
