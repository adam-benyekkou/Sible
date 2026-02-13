# Security and Governance

Sible is built with a security-first mindset, incorporating granular access controls and automated audit gates.

## Multi-Tiered RBAC
Access control is enforced through a granular three-tier Role-Based Access Control (RBAC) system:
*   **Admin**: Complete system configuration, user lifecycle management, and execution rights.
*   **Operator**: Execution-level access for playbook triggering and inventory management.
*   **Watcher**: Read-only access for monitoring status and auditing execution logs.

## Just-in-Time (JIT) Secret Injection
Sible implements ephemeral payload injection for sensitive data. Secrets are securely injected into Ansible templates at runtime and are never persisted in plain text on the local filesystem. This mechanism ensures that credentials exist only within the memory space of the active execution process.

## Integrated Secret Vaulting
Sensitive credentials—including SSH private keys, API tokens, and cloud provider secrets—are managed through an internal encrypted vault. This centralized management layer ensures that all operational targets are authenticated securely without exposing credentials to the end user.

## Security Audit Gates
Continuous security validation is integrated via GitHub Actions. Every release is analyzed by a comprehensive suite of audit tools:
*   **Gitleaks**: Detection of hardcoded secrets.
*   **Bandit**: Static Analysis Security Testing (SAST) for Python logic.
*   **Safety**: Dependency vulnerability scanning.
*   **Trivy**: Container filesystem and image layer security auditing.

## Hardened Production Execution
Sible adheres to the principle of least privilege. The Docker implementation is designed for non-root execution by default, significantly reducing the attack surface and ensuring compliance with modern container security standards.
