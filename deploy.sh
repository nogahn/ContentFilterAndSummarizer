#!/bin/bash

# Stack name
STACK_NAME="llm-app"

# Build the Docker image
echo "Building Docker image..."
docker build -t llm-app:latest .

# Set environment variables for the stack deployment
export APP_IMAGE="llm-app:latest"

# LLM Configuration
export LLM_PROVIDER="groq"
# export LLM_MODEL_NAME="llama3-8b-8192"
# export LLM_TEMPERATURE=0.3
# export LLM_MAX_TOKENS=512

# API Keys (replace with your actual keys)
export GROQ_API_KEY="your-groq-api-key"
# export OPENAI_API_KEY="your-openai-api-key"
# export GOOGLE_API_KEY="your-google-api-key"
# export ANTHROPIC_API_KEY="your-anthropic-api-key"

# RabbitMQ Configuration
# export RABBITMQ_USER="guest"
# export RABBITMQ_PASSWORD="guest"

# Worker Configuration
export PROCESSOR_PREFETCH_COUNT=1
export EVALUATOR_PREFETCH_COUNT=1
export WEBSOCKET_CONSUMER_PREFETCH_COUNT=10
export EVALUATOR_SCORE_THRESHOLD=7.0
export MAX_RETRIES_URL_TASK=3
export MAX_RETRIES_EVALUATION_TASK=3

# Initialize Docker Swarm if not already initialized
if ! docker info | grep -q "Swarm: active"; then
  echo "Initializing Docker Swarm..."
  docker swarm init
fi

# Deploy the stack with environment variables
echo "Deploying stack: $STACK_NAME"
docker stack deploy -c docker-compose.yml $STACK_NAME

echo "Stack deployed successfully!"
echo "Access the application at http://localhost:8000"
