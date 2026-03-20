#!/bin/bash

# AQMS (AI Query Migration System) - 통합 빌드 스크립트

echo "📦 Building Frontend Assets..."
cd frontend
npm install
npm run build

echo "✅ Build Complete!"
echo "Assets are located in: frontend/dist"
