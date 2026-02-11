# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of Sible seriously. If you believe you have found a security vulnerability, please report it to us by emailing **<cavy.protocol.dev@proton.me>**.

**Please do not report security vulnerabilities via public GitHub issues.**

What to include in your report:

- A description of the vulnerability and its potential impact.
- Steps to reproduce the issue.
- Any suggested fixes or mitigations.

We will acknowledge receipt of your report within 48 hours and provide a timeline for a resolution.

## Security Philosophy

Sible is designed with "Local First" infrastructure in mind.

- **Isolation**: We prioritize local paths and Docker volumes over external GitOps syncs for sensitive playbooks to prevent accidental exposure of keys in Git history.
- **Minimalism**: The core application runs with minimal privileges and uses strict path validation to prevent directory traversal.
- **Transparency**: All execution logs are stored locally and accessible only to authorized operators.
