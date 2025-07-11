#!/bin/bash

STACK_NAME="llm-app"

if docker stack ls | grep -q $STACK_NAME; then
  echo "Stopping stack: $STACK_NAME"
  docker stack rm $STACK_NAME
  
  echo "Waiting for services to be removed..."
  while docker service ls | grep -q $STACK_NAME; do
    echo "Services still running, waiting..."
    sleep 2
  done
fi

echo "Waiting for resources to be released..."
sleep 5

echo "Pruning all resources associated with the stack..."
docker system prune -f --volumes --filter "label=com.docker.stack.namespace=$STACK_NAME"


read -p "Do you want to leave swarm mode? (y/n): " leave_swarm
if [ "$leave_swarm" = "y" ]; then
  echo "Leaving swarm mode..."
  docker swarm leave --force
fi

echo "Cleanup completed successfully!"