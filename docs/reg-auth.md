# Registration, Login, Membership Check, and GDPR Notes

## Prompt (from user)
I want to create a user registration and login page.

I want users to be able to log in with a username and password as follows:
- using their email address as username. They will need to click a link in an email to confirm the address.
- Just using a nickname and password. They can add an email address later. They will then need to click on a link to confirm.
- I also want people to be able to submit information anonymously as they can now.

I want to check email addresses against a copy of membermojo email addresses. It will not be essential to be in the membermojo list but I want to mark them as a member.

I believe we will need to implement GDPR functions. I believe these include:
- a user can request to receive a copy of all their data
- a user can request to remove all their data.
- can you list any others.
- I assume we need a GDPR policy. Can you write or copy an appropriate one for a small sports user group and put it in www-root. It should be in the name of HMPA - Highgate Men's Pond Association. It should refer to data held on Membermojo, and pond status updates held in the pond website (currently ponds.nsupdate.info)

Please record this in prompt and your response in a docs/reg-auth.md.

## Response
Implemented a first-pass registration and login flow with anonymous submissions preserved.

### What is now implemented
- Account registration by email and password.
- Account registration by nickname and password.
- Email verification token flow with verification link endpoint.
- Add/update email after nickname-only registration, followed by verification.
- Login using username field (email or nickname).
- Account profile endpoint to fetch membership and verification status.
- Membership marking by checking the latest file matching membermojo/membermojo-*.csv.
- Anonymous pond submission endpoint remains available.
- Basic registration/login UI page added.
- Email verification landing page added.
- GDPR policy page added in www-root.

### New endpoints
- POST /api/auth/register-email
- POST /api/auth/register-nickname
- POST /api/auth/login
- POST /api/auth/add-email
- GET /api/auth/verify-email
- GET /api/auth/me

### Membership check behavior
- On registration or email update/verification, the service loads the latest membermojo/membermojo-*.csv file.
- If the email appears in that file, isMember is set true for the account.
- Membership match is informative only, not required for account creation.

### Email confirmation details
- Confirmation links are generated and written to logs/auth-email-outbox.log.
- This is a local outbox stub and should be replaced with real email delivery (SMTP/API) for production notifications.

### GDPR functions requested and additional recommended rights/workflows
Requested:
- data copy export for a user
- data erasure for a user

Additional GDPR rights/workflows to implement:
- rectification (correct inaccurate account data)
- restriction of processing
- objection to legitimate-interest processing
- portability (machine-readable export)
- consent withdrawal where consent is the lawful basis
- records of processing activities and retention schedule
- lawful basis mapping per data type
- security incident/breach response process
- DPA/processor agreement review for third parties

### GDPR policy file
- Added policy page: www-root/gdpr-policy.html
- Policy is in the name of HMPA and references:
  - member data in MemberMojo
  - pond status data on ponds.nsupdate.info

### Notes for next phase
- Wire real transactional email provider for verification emails.
- Add authenticated linkage between pond submissions and user accounts where desired.
- Add explicit API routes for GDPR export and deletion actions.
- Add abuse controls (rate limits, lockout, token rotation, CSRF considerations if cookie auth is introduced).
