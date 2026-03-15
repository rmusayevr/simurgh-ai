# Security Policy

## Supported Versions

Only the latest version of this project currently receives security fixes.

| Version | Supported |
|---|---|
| Latest (`main`) | ✅ |
| Older commits | ❌ |

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.** Public disclosure before a fix is in place puts all users at risk.

Instead, send a private email to:

**rashadmusayev03@gmail.com**

### What to include in your report

To help investigate and reproduce the issue quickly, please include as much of the following as possible:

- A clear description of the vulnerability and its potential impact
- The affected component (e.g. authentication, RAG pipeline, admin endpoints)
- Step-by-step instructions to reproduce the issue
- Any proof-of-concept code or screenshots if applicable
- Your suggested fix, if you have one

---

## Response Timeline

| Stage | Timeframe |
|---|---|
| Initial acknowledgement | Within 7 days |
| Confirmation of the issue | Within 14 days |
| Fix or mitigation released | Depends on severity (see below) |

### Severity-based fix timeline

| Severity | Description | Target Fix Time |
|---|---|---|
| **Critical** | Remote code execution, auth bypass, data exposure | Within 7 days |
| **High** | Privilege escalation, sensitive data leakage | Within 14 days |
| **Medium** | Limited impact, requires specific conditions | Within 30 days |
| **Low** | Minimal risk, cosmetic or theoretical | Next scheduled release |

---

## Scope

The following are **in scope** for security reports:

- Authentication and authorisation (JWT handling, role-based access control)
- API endpoints exposing sensitive data
- RAG pipeline cross-project data leakage
- Prompt injection vulnerabilities in AI inputs
- Encryption of sensitive stakeholder data at rest
- Admin console access control
- Docker configuration exposing services unintentionally

The following are **out of scope:**

- AI-generated content being factually incorrect or misleading (this is a known limitation of LLMs, not a security vulnerability)
- Rate limiting bypass through legitimate usage patterns (e.g. many users behind a shared IP)
- Vulnerabilities in third-party dependencies that have no available fix yet
- Issues requiring physical access to the server
- Social engineering attacks

---

## Disclosure Policy

Once a fix has been released, we aim to publish a brief security advisory on the GitHub repository at:

[https://github.com/rmusayevr/simurgh-ai/security/advisories](https://github.com/rmusayevr/simurgh-ai/security/advisories)

We kindly ask that you give us reasonable time to release a fix before any public disclosure. We will credit you in the advisory unless you prefer to remain anonymous.

---

## Thank You

Responsible disclosure helps keep this project and its users safe. We genuinely appreciate the time and effort security researchers put into finding and reporting issues.