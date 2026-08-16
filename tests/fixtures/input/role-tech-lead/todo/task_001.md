# Tech Lead Review: Authentication Module

## Key Concerns
1. HMAC secret defaults to 'changeme' — must require environment override in production.
2. In-memory UserRepository lacks persistent database adapter.
3. Add rate limiting to AuthService.login to prevent brute-force attacks.
