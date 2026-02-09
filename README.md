# Copilot Terraform Agent

🤖 AI-powered Terraform code generator for Microsoft Copilot Studio

## Overview

This is a lightweight API that generates Azure Terraform code using Azure OpenAI. It's designed to work with Microsoft Copilot Studio as a backend service.

## Architecture

```
┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│   Copilot Studio    │ ──── │   This API          │ ──── │   Azure OpenAI      │
│   (Teams/Web)       │      │   (Flask App)       │      │   (GPT-4o)          │
└─────────────────────┘      └─────────────────────┘      └─────────────────────┘
                                      │
                                      ▼
                             ┌─────────────────────┐
                             │   GitHub PR         │
                             │   (Optional)        │
                             └─────────────────────┘
```

## Key Difference from Foundry Agent

| Feature | This App (Copilot Agent) | Foundry App |
|---------|--------------------------|-------------|
| AI Backend | Azure OpenAI directly | Azure AI Foundry Agent |
| Dependencies | Minimal (openai SDK) | Azure AI Projects SDK |
| Complexity | Simple | More features |
| Use Case | Copilot Studio integration | Full web app |

## Quick Start

### 1. Clone and Setup

```bash
# Clone repository
git clone https://github.com/gethiten/copilot-terraform-agent.git
cd copilot-terraform-agent

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example config
copy .env.example .env

# Edit with your values
notepad .env
```

Required settings:
- `AZURE_OPENAI_ENDPOINT` - Your Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY` - Your Azure OpenAI API key
- `AZURE_OPENAI_DEPLOYMENT` - Model deployment name (e.g., gpt-4o)

Optional (for PR creation):
- `GITHUB_TOKEN` - GitHub personal access token
- `GITHUB_REPO_URL` - Your repository URL

### 3. Run Locally

```bash
python app.py
```

Open http://localhost:5001 in your browser.

### 4. Test the API

```bash
# Health check
curl http://localhost:5001/api/health

# Generate Terraform
curl -X POST http://localhost:5001/api/copilot/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a storage account", "location": "eastus"}'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/copilot/generate` | POST | Generate Terraform code |
| `/api/copilot/status/{pr}` | GET | Check PR status |
| `/api/templates` | GET | List available templates |

## Copilot Studio Integration

### 1. Deploy to Azure

```bash
# Create App Service
az webapp create --name copilot-terraform-agent \
  --resource-group rg-copilot \
  --plan my-plan \
  --runtime "PYTHON:3.11"

# Configure settings
az webapp config appsettings set --name copilot-terraform-agent \
  --resource-group rg-copilot \
  --settings AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=...
```

### 2. Create Custom Connector

1. Go to [Power Automate](https://make.powerautomate.com)
2. Navigate to **Custom connectors**
3. Import `docs/copilot-openapi.json`
4. Update the host to your App Service URL

### 3. Create Copilot Studio Agent

1. Go to [Copilot Studio](https://copilotstudio.microsoft.com)
2. Create new copilot
3. Add topic with trigger phrases like "create infrastructure"
4. Call the custom connector action

## Files

```
copilot-terraform-agent/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── .env.example             # Environment template
├── .gitignore               # Git ignore rules
├── templates/
│   └── index.html           # Web interface
└── docs/
    └── copilot-openapi.json # OpenAPI spec for Copilot
```

## License

MIT
