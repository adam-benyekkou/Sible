# Core Orchestration

Sible provides a robust execution layer for Ansible playbooks, focusing on performance, parallelization, and real-time visibility.

## Asynchronous Log Streaming
Real-time execution visibility is facilitated via a low-latency WebSocket implementation. Sible streams Ansible subprocess output directly to the UI, ensuring immediate operational feedback and eliminating the overhead associated with traditional log polling.

## Native Subprocess Management
Sible orchestrates Ansible through a controlled subprocess layer, ensuring full compatibility with the existing Ansible ecosystem. It dynamically manages environment variables, inventory paths, and vaulted credentials to maintain a seamless bridge between the FastAPI backend and the Ansible engine.

## Multi-Node Targeting
Sible supports parallel execution across distributed infrastructure. Playbooks can be targeted against specific servers, arbitrary host ranges, or predefined inventory groups simultaneously, enabling rapid deployment and configuration management across global environments.

## SSH Connection Lifecycle Management
The engine provides granular control over the SSH lifecycle for remote targets. This includes support for custom SSH ports, specific user configurations, and managed key-based authentication, allowing for flexible connectivity across heterogeneous network environments.

## Infrastructure Volume Strategy
To ensure persistence and portability, Sible utilizes a dedicated Infrastructure Volume strategy. By mounting `/app/infrastructure`, the system enforces a strict separation between application logic and user-defined playbooks, roles, and inventories, facilitating streamlined backups and multi-environment consistency.
