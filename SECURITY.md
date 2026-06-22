# Security Policy

## Supported Versions

Currently, only the latest version of the **Kayfa AI Sales Agent & CRM** receives security updates. 

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

Security is a top priority for this project. If you discover a security vulnerability within this application (e.g., issues related to Authentication, Database access, or LLM Prompt Injection), please **do not** disclose it publicly by creating a GitHub Issue.

Instead, please report it privately by sending an email to:
**somiamoslhy@gmail.com**

### What to include in your report:
* A detailed description of the vulnerability.
* Steps to reproduce the issue.
* Potential impact of the vulnerability.

I will acknowledge receipt of your vulnerability report within 48 hours and strive to send you regular updates about our progress in fixing it.

## Project-Specific Security Notes

If you are forking or deploying this project, please adhere to the following security practices:

1. **Environment Variables (`.env`):** Never commit your `.env` file or hardcode sensitive credentials. Ensure that your LLM API Keys (e.g., Gemini/Claude) and `MONGODB_URI` are kept strictly confidential.
2. **Database Security:** The `MongoDBHandler` is configured to use TLS (`certifi`). Ensure your MongoDB Atlas cluster has strict IP Access List rules (e.g., whitelisting only your deployment server's IP).
3. **Role-Based Access Control (RBAC):** The application uses session states to manage access to the CRM dashboard. Always change the default `APP_EMAIL` and `APP_PASSWORD` environment variables before deploying to production.
