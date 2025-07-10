#!/bin/bash

# Start backend in background
echo "Starting backend..."
python -m risklive.server.app &

# Wait until backend health endpoint is ready
echo "Waiting for backend to be ready..."
until curl -s http://localhost:5000/health; do
  echo "Backend not ready, waiting 2 seconds..."
  sleep 2
done

# Start Streamlit dashboard (foreground)
echo "Starting dashboard..."
streamlit run risklive/dashboard/TopicModel.py --server.port=8501 --server.address=0.0.0.0
