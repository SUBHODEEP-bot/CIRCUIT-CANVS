#!/bin/bash
# Render Deployment Setup Script

echo "🚀 CircuitForge Lab - Render Deployment Setup"
echo "=============================================="
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your Supabase credentials."
    echo ""
    read -p "Press Enter after updating .env with your credentials..."
fi

# Check if frontend .env exists
if [ ! -f "circuit-canvas/.env" ]; then
    echo "⚠️  No frontend .env file found. Creating from template..."
    cp circuit-canvas/.env.example circuit-canvas/.env
    echo "✅ Created circuit-canvas/.env file. Using same Supabase credentials..."
fi

echo ""
echo "📦 Installing Python dependencies..."
pip install -q -r requirements.txt

echo "📦 Installing Node dependencies..."
cd circuit-canvas
npm install --quiet
echo ""

echo "🔨 Building frontend..."
npm run build

cd ..

echo ""
echo "✅ Setup Complete!"
echo ""
echo "📋 Deployment Checklist:"
echo "  ☐ Frontend built successfully (check circuit-canvas/dist/)"
echo "  ☐ .env file configured with Supabase credentials"
echo "  ☐ Git repository initialized and pushed to GitHub"
echo "  ☐ Render account created at render.com"
echo ""
echo "🚀 Next Steps:"
echo "  1. Push your code to GitHub:"
echo "     git add ."
echo "     git commit -m 'Initial commit'"
echo "     git push origin main"
echo ""
echo "  2. On Render Dashboard:"
echo "     - Create new Web Service"
echo "     - Connect your GitHub repository"
echo "     - Set environment variables (from .env.example)"
echo "     - Set build command (see DEPLOYMENT.md)"
echo "     - Deploy!"
echo ""
echo "📖 For detailed instructions, see DEPLOYMENT.md"
echo ""
