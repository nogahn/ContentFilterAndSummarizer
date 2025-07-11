#!/bin/bash

echo "LLM Application Restart Options:"
echo "1. Stop and redeploy (preserves data)"
echo "2. Clean everything and deploy fresh (removes all data)"
read -p "Select an option (1/2): " restart_option

case $restart_option in
    1)
        echo "Stopping and redeploying with preserved data..."
        ./stop.sh
        ./deploy.sh
        ;;
    2)
        echo "Cleaning everything and deploying fresh..."
        ./cleanup.sh
        ./deploy.sh
        ;;
    *)
        echo "Invalid option. Exiting."
        exit 1
        ;;
esac

echo "Restart process completed!"