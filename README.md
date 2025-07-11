# LLM Content Processing System: Setup & Deployment Guide

This guide provides the essential steps to quickly get your distributed LLM content processing system up and running.

For an in-depth understanding of the system's architecture and components, please refer to the dedicated [Architecture Document](architecture.md).

---

## 1. Prerequisites

Before you start, make sure you have the following installed on your system:

* **Docker**: This project is containerized and deployed using Docker (via Docker Swarm stack). Ensure **Docker Engine** is installed and running (e.g., Docker Desktop on Windows/macOS, or Docker Engine directly on Linux/WSL).
* **Git**: For cloning the repository.
* **Bash Environment**: A Bash-compatible shell (e.g., Git Bash on Windows, Terminal on Linux/macOS) is required to run the provided shell scripts.

---

## 2. Environment Variables Configuration

The system relies on several environment variables for configuration, particularly for LLM API keys, LLM model settings, and RabbitMQ connection details. These are managed within the `deploy.sh` script and sourced from your shell environment.

* **Open the `deploy.sh` file**.
* **Replace** the placeholder `GROQ_API_KEY` (or any other LLM API key) with your actual key.
* **If you wish to use a different LLM provider** (e.g., OpenAI, Google, Anthropic), or customize RabbitMQ credentials/worker settings, **uncomment** and configure the relevant variables in the file.

**Important Note on LLM Configuration:**
By default, the system runs with a single LLM configuration (`LLM_PROVIDER`, `LLM_MODEL_NAME`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`) applied to all LLM-dependent services (Processor and Evaluator).
If you require the Processor and Evaluator services to use **different LLM models or providers simultaneously**, you must override these variables directly in the `docker-compose.yml` for each specific service. This would involve adding an `environment` block under the respective service (e.g., `processor` or `evaluator`) and specifying the `LLM_PROVIDER`, `LLM_MODEL_NAME`, and the corresponding `API_KEY` (e.g., `OPENAI_API_KEY`) there.

* **Crucial Note**: Any changes to environment variables in `deploy.sh`, `Dockerfile`, or `docker-compose.yml` **require a full cleanup** of the system before redeploying (see Section 4.3).

---

## 3. Running the System

First, make all deployment and management scripts executable:

```
chmod +x deploy.sh stop.sh cleanup.sh restart.sh
```


Now, navigate to the root directory of your project (where `docker-compose.yml` and `deploy.sh` are located) and execute the deployment script:
```
./deploy.sh
```


This script will build the Docker images, initialize Docker Swarm (if not active), and deploy all system services as a Docker stack.

---

## 4. Managing the System

### 4.1. Accessing the Application

Once deployed, the web interface will be available at:
[http://localhost:8000](http://localhost:8000)

### 4.2. Stopping the System

To stop all services while **preserving your RabbitMQ and Redis data**:

```
./stop.sh
```


### 4.3. Full Cleanup and Reset

To completely stop the system, **delete all data**, remove Docker images, and optionally leave Swarm mode:

```
./cleanup.sh
```


**Essential**: Always use this script **before redeploying** if you've made changes to environment variables, `Dockerfile`, or `docker-compose.yml` to prevent conflicts and ensure a clean setup.

### 4.4. Restarting the System

You can use the `restart.sh` script to conveniently stop and redeploy your application with different options:
```
./restart.sh
```

This script will present you with two choices:
1.  **Stop and redeploy (preserves data):** This runs `./stop.sh` followed by `./deploy.sh`, keeping your RabbitMQ and Redis data intact.
2.  **Clean everything and deploy fresh (removes all data):** This runs `./cleanup.sh` followed by `./deploy.sh`, performing a full reset including data removal.


---

## 5. Troubleshooting Common Issues

* **Services not starting or disconnecting**:
    * Ensure your LLM API keys are valid and correctly configured in `deploy.sh` (or `docker-compose.yml` if overridden).
    * Check Docker service logs for specific errors: `docker service logs <service_name>` (e.g., `docker service logs llm-app_server`).
* **Environment variable changes not taking effect**: As noted in Section 4.3, you **must** run `cleanup.sh` followed by `deploy.sh` after any variable modifications to ensure a fresh deployment.