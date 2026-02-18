# Copilot Studio Setup Guide

This guide walks you through setting up Microsoft Copilot Studio agent that generates Terraform code directly (no external AI dependency).

## Architecture (Simplified)

```
User → Copilot Studio (GPT generates Terraform) → Action → Backend API → GitHub PR
```

**Key benefits:**
- No Power Automate flows needed
- No manual topic flows required
- Copilot Studio's GPT handles everything
- Actions call your API directly

## Prerequisites

1. **Microsoft 365 license** with Copilot Studio access
2. This API deployed (see [README.md](../README.md))
3. **GitHub repository** for storing Terraform code

**Not required:**
- ❌ Power Automate license
- ❌ Azure OpenAI
- ❌ Azure AI Foundry

---

## Step 1: Deploy the API to Azure App Service

> **Note**: This creates a NEW, separate deployment from the Foundry Agent app.
> You will have two independent apps:
> - `rg-foundry-terraform` - Foundry Agent (existing)
> - `rg-copilot-terraform` - Copilot Studio Agent (this guide)

```powershell
# =============================================================================
# CREATE NEW RESOURCE GROUP (separate from Foundry app)
# =============================================================================

# Create dedicated resource group for Copilot Studio agent
az group create --name rg-copilot-terraform --location eastus

# Create App Service plan (dedicated to this app)
az appservice plan create --name plan-copilot-terraform \
  --resource-group rg-copilot-terraform \
  --sku B1 --is-linux

# Create web app with unique name
az webapp create --name copilot-terraform-agent \
  --resource-group rg-copilot-terraform \
  --plan plan-copilot-terraform \
  --runtime "PYTHON:3.11"

# Configure settings (only GitHub - no Azure OpenAI needed!)
az webapp config appsettings set --name copilot-terraform-agent \
  --resource-group rg-copilot-terraform \
  --settings \
    GITHUB_TOKEN="ghp_your_token" \
    GITHUB_REPO_URL="https://github.com/your-org/terraform-deployments"

# Deploy code via local git
az webapp deployment source config-local-git --name copilot-terraform-agent \
  --resource-group rg-copilot-terraform

# Get the git remote URL
az webapp deployment list-publishing-credentials --name copilot-terraform-agent \
  --resource-group rg-copilot-terraform --query scmUri -o tsv

# Add as git remote and push
git remote add azure <scm-url-from-above>
git push azure main
```

---

## Step 2: Create Copilot Studio Agent with Actions

### 2.1 Create New Copilot

1. Go to [Copilot Studio](https://copilotstudio.microsoft.com)
2. Click **+ Create** → **New agent**
3. Configure:
   - Name: `Terraform Infrastructure Bot`
   - Description: `AI assistant that generates Azure infrastructure using Terraform`
   - Language: English

### 2.2 Add the API as an Action

1. In your copilot, go to **Actions** → **+ Add an action**
2. Select **Create a new action** → **Connector action**
3. Choose **Import from OpenAPI**
4. Upload [copilot-openapi.json](./copilot-openapi.json)
5. Configure connection:
   | Setting | Value |
   |---------|-------|
   | Host | `copilot-terraform-agent.azurewebsites.net` (your deployed API) |
   | Scheme | HTTPS |
6. Review operations and click **Create**

The following actions are now available to your copilot:
- `commitTerraform` - Commit Terraform code to GitHub
- `getPRStatus` - Check PR status
- `listTemplates` - List infrastructure templates

### 2.3 Configure Agent Instructions

Go to **Overview** → **Instructions** and add:

```
You are an expert Azure Infrastructure Engineer and Terraform specialist.
Your role is to generate production-ready Terraform code for Azure resources.

## YOUR CAPABILITIES
1. Generate complete, valid Terraform code for any Azure resource
2. Follow Azure and Terraform best practices
3. Use the commitTerraform action to save code to GitHub
4. Check PR status with getPRStatus action
5. Show available templates with listTemplates action

## TERRAFORM CODE RULES
1. Always use AzureRM provider version ~> 4.0
2. Include provider configuration with subscription_id variable
3. Define all variables with descriptions and sensible defaults
4. Add meaningful outputs for created resources
5. Follow Azure naming conventions (lowercase, hyphens)
6. Include tags for resource management

## WORKFLOW
When a user asks to create Azure resources:
1. Clarify what they need if unclear
2. Ask for preferred Azure region (default: eastus)
3. Generate complete Terraform code
4. Call commitTerraform action with the code
5. Share the PR link for review

## PROVIDER TEMPLATE
Always include this in your Terraform code:

terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}
```

### 2.4 Enable Generative AI

1. Go to **Settings** → **Generative AI**
2. Enable **Use generative AI**
3. Set orchestration to **Generative (preview)** or **Classic + Generative**

This allows the copilot to:
- Understand user intent automatically
- Generate Terraform code using built-in GPT
- Decide when to call actions

---

## Step 3: Test the Agent

### 3.1 Test in Copilot Studio

1. Click **Test** in the top-right
2. Try these prompts:
   - `Create a storage account in eastus`
   - `Deploy a Linux VM with public IP`
   - `Create an AKS cluster with 3 nodes`

### 3.2 Example Conversation

```
User: Create a storage account with blob container

Copilot: I'll create Terraform code for an Azure Storage Account with a blob container.
         Which Azure region would you like to use? (default: eastus)

User: westus2

Copilot: I've generated the Terraform code and committed it to GitHub.

         ✅ Pull Request created: https://github.com/your-org/repo/pull/5

         The PR includes:
         - providers.tf - Azure provider configuration
         - variables.tf - Input variables
         - main.tf - Storage account and blob container
         - outputs.tf - Resource outputs

         Next steps:
         1. Review the code in the PR
         2. Approve and merge
         3. GitHub Actions will deploy your infrastructure
```

---

## Step 4: Deploy to Teams (Optional)

### 4.1 Publish Copilot

1. Go to **Publish** in Copilot Studio
2. Click **Publish** to make changes live

### 4.2 Add to Teams

1. Go to **Channels** → **Microsoft Teams**
2. Click **Turn on Teams**
3. Follow the prompts to add to Teams

Users can now chat with the bot directly in Microsoft Teams!

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "terraform_code is required" error | Ensure Copilot generates code before calling the action |
| PR not created | Check GITHUB_TOKEN is set in App Service |
| Action not appearing | Re-import the OpenAPI spec |
| Invalid Terraform syntax | Review agent instructions |
| Connection error | Verify API URL in action configuration |

### Debug Steps

1. Check API health: `https://your-app.azurewebsites.net/api/health`
2. View App Service logs: `az webapp log tail --name copilot-terraform-agent --resource-group rg-copilot-terraform`
3. Test API directly with curl before using in Copilot

---

## Security Recommendations

1. **API Authentication**: Add API key authentication to the action
2. **Rate Limiting**: Implement rate limits to prevent abuse
3. **PR Reviews**: Require PR approval before Terraform deployment
4. **Audit Logging**: Monitor all API requests
5. **Secrets**: Use Azure Key Vault for sensitive values

---

## Architecture Comparison

### This Project (Copilot Studio with Actions) - SIMPLE
```
User → Copilot Studio → Action → Backend API → GitHub PR
         (GPT)         (direct)   (Flask)
```

**Benefits:**
- No Power Automate flows needed
- No Azure OpenAI costs
- No Foundry dependency
- Simplest setup
- All AI logic in Copilot Studio

### Alternative: Foundry Agent
```
Web App → Flask API → Azure AI Foundry Agent → GPT-4o → GitHub PR
```

**When to use which:**
- **Copilot Studio + Actions (this project)**: Teams integration, simplest setup, no extra costs
- **Foundry Agent**: Custom web app, advanced agent features, tool calling

---

## Files Reference

| File | Description |
|------|-------------|
| `app.py` | Main Flask application |
| `docs/copilot-openapi.json` | OpenAPI spec for custom connector |
| `templates/index.html` | Web test interface |
| `.env.example` | Environment variables template |
