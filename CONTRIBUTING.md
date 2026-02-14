# Contributing to Sible

First off, thank you for considering contributing to Sible! It's people like you that make Sible such a great tool.

## Philosophy

Sible follows the **Zero-Bloat** philosophy. We prioritize:
- **Simplicity**: No complex build steps (webpack/npm) unless absolutely necessary.
- **Performance**: HTMX and server-side rendering over heavy SPAs.
- **Security**: Hardened defaults and minimal dependencies.

## Development Setup

Sible is a Python-first project. You don't need Node.js unless you are working on the documentation.

### Prerequisites
- Python 3.11+
- Docker (optional, for running Ansible in isolation)

### Steps

1.  **Fork and Clone**
    ```bash
    git clone https://github.com/YOUR_USERNAME/Sible.git
    cd Sible
    ```

2.  **Create Virtual Environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run Development Server**
    ```bash
    uvicorn app.main:app --reload
    ```
    The app will be available at `http://localhost:8000`.

## Project Structure

- `app/`: Core application logic (FastAPI)
  - `routers/`: API endpoints and HTML view controllers
  - `services/`: Business logic (Runner, Inventory, etc.)
  - `models/`: SQLModel database schemas
- `templates/`: Jinja2 HTML templates (The UI)
- `static/`: CSS (PicoCSS), JS (Alpine.js), and images
- `playbooks/`: Default playbook directory

## Code Style

- **Python**: We follow PEP 8. Please run `ruff check .` before submitting.
- **HTML/CSS**: Keep classes semantic. We use [PicoCSS](https://picocss.com/) for styling.
- **Commits**: Use [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat: add new sidebar`, `fix: resolve ssh connection bug`).

## Pull Request Process

1.  Ensure any install or build dependencies are removed before the end of the layer when doing a build.
2.  Update the README.md with details of changes to the interface, this includes new environment variables, exposed ports, useful file locations and container parameters.
3.  Increase the version numbers in any examples files and the README.md to the new version that this Pull Request would represent.
4.  You may merge the Pull Request in once you have the sign-off of two other developers, or if you do not have permission to do that, you may request the second reviewer to merge it for you.
