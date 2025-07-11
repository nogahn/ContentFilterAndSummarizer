#!/bin/bash

STACK_NAME="llm-app"

# Stop the stack
echo "Stopping stack: $STACK_NAME"
docker stack rm $STACK_NAME

# Wait for services to be removed
echo "Waiting for services to be removed..."
while docker service ls | grep -q $STACK_NAME; do
  echo "Services still running, waiting..."
  sleep 2
done

echo "Stack stopped successfully!"
