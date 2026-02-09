# Copilot Studio Setup Guide

This guide walks you through setting up Microsoft Copilot Studio with the Copilot Terraform Agent.

## Prerequisites

1. **Microsoft 365 license** with Copilot Studio access
2. **Power Automate** license (included with most M365 plans)
3. **Azure OpenAI** resource with GPT-4o deployment
4. This API deployed (see [README.md](../README.md))

---

## Step 1: Deploy the API to Azure

### Option A: Azure App Service

```powershell
# Create resource group
az group create --name rg-copilot-terraform --location eastus

# Create App Service plan
az appservice plan create --name plan-copilot-terraform \
  --resource-group rg-copilot-terraform \
  --sku B1 --is-linux

# Create web app
az webapp create --name copilot-terraform-agent \
  --resource-group rg-copilot-terraform \
  --plan plan-copilot-terraform \
  --runtime "PYTHON:3.11"

# Configure settings
az webapp config appsettings set --name copilot-terraform-agent \
  --resource-group rg-copilot-terraform \
  --settings \
    AZURE_OPENAI_ENDPOINT="https://your-openai.openai.azure.com/" \
    AZURE_OPENAI_API_KEY="your-key" \
    AZURE_OPENAI_DEPLOYMENT="gpt-4o" \
    GITHUB_TOKEN="ghp_your_token" \
    GITHUB_REPO_URL="https://github.com/gethiten/copilot-terraform-agent"

# Deploy code
az webapp deployment source config-local-git --name copilot-terraform-agent \
  --resource-group rg-copilot-terraform
```

### Option B: Azure Container Apps

```powershell
# Build and push container
docker build -t copilot-terraform-agent .
az acr login --name yourregistry
docker tag copilot-terraform-agent yourregistry.azurecr.io/copilot-terraform-agent:v1
docker push yourregistry.azurecr.io/copilot-terraform-agent:v1

# Deploy to Container Apps
az containerapp create --name copilot-terraform-agent \
  --resource-group rg-copilot-terraform \
  --image yourregistry.azurecr.io/copilot-terraform-agent:v1 \
  --environment my-environment \
  --ingress external --target-port 5001
```

---

## Step 2: Create Custom Connector in Power Platform

### 2.1 Navigate to Custom Connectors

1. Go to [Power Automate](https://make.powerautomate.com)
2. Click **More** → **Discover all** → **Custom connectors**
3. Click **+ New custom connector** → **Import an OpenAPI file**

### 2.2 Import OpenAPI Specification

1. Name: `Copilot Terraform Agent`
2. Upload: [copilot-openapi.json](./copilot-openapi.json)
3. Click **Continue**

### 2.3 Configure General Settings

| Setting | Value |
|---------|-------|
| Scheme | HTTPS |
| Host | `copilot-terraform-agent.azurewebsites.net` |
| Base URL | `/` |

### 2.4 Security (Optional)

For production, add API Key authentication:

1. Authentication type: **API Key**
2. Parameter label: `API Key`
3. Parameter name: `X-API-Key`
4. Location: **Header**

### 2.5 Create Connector

1. Review operations:
   - `generateTerraform` (POST)
   - `getPRStatus` (GET)
   - `healthCheck` (GET)
   - `listTemplates` (GET)
2. Click **Create connector**
3. Test using the **Test** tab

---

## Step 3: Create Power Automate Flow

### 3.1 Create New Flow

1. Go to [Power Automate](https://make.powerautomate.com)
2. Click **+ Create** → **Instant cloud flow**
3. Name: `Generate Terraform from Copilot`
4. Trigger: **When a HTTP request is received**

### 3.2 Configure HTTP Trigger

Request body JSON schema:
```json
{
    "type": "object",
    "properties": {
        "prompt": { "type": "string" },
        "location": { "type": "string" },
        "email": { "type": "string" }
    },
    "required": ["prompt"]
}
```

### 3.3 Add Action: Generate Terraform

1. Add action: **Copilot Terraform Agent** → **generateTerraform**
2. Map fields:
   - **prompt**: `@{triggerBody()?['prompt']}`
   - **location**: `@{coalesce(triggerBody()?['location'], 'eastus')}`
   - **create_pr**: `true`

### 3.4 Add Response Action

1. Add action: **Response**
2. Status Code: `200`
3. Body:
```json
{
    "success": "@{body('generateTerraform')?['success']}",
    "message": "@{body('generateTerraform')?['message']}",
    "pr_url": "@{body('generateTerraform')?['pr_url']}"
}
```

### 3.5 Save and Get URL

1. Save the flow
2. Copy the **HTTP POST URL** - you'll need this for Copilot Studio

---

## Step 4: Create Copilot Studio Agent

### 4.1 Create New Copilot

1. Go to [Copilot Studio](https://copilotstudio.microsoft.com)
2. Click **+ Create** → **New copilot**
3. Configure:
   - Name: `Terraform Infrastructure Bot`
   - Description: `AI assistant that generates Azure infrastructure using Terraform`
   - Language: English

### 4.2 Configure System Instructions

Go to **Settings** → **Generative AI** and add:

```
You are an Azure infrastructure provisioning assistant. You help users create Azure resources by generating Terraform code.

When a user asks to create Azure resources:
1. Ask what resources they need
2. Ask for the preferred Azure region
3. Generate the Terraform code using the backend API
4. Provide the GitHub PR link for review

Be helpful and explain what resources will be created.
```

### 4.3 Create "Generate Terraform" Topic

1. Go to **Topics** → **+ Add** → **From blank**
2. Name: `Generate Terraform Infrastructure`

#### Trigger Phrases
- create a storage account
- deploy a virtual machine
- create azure infrastructure
- generate terraform
- provision a function app
- create a web app

#### Topic Flow

**1. Message Node**
```
I'll help you create Azure infrastructure! Let me gather a few details.
```

**2. Question Node - Resources**
- Question: `What Azure resources would you like to create?`
- Save as: `Topic.Prompt`

**3. Question Node - Location**
- Question: `Which Azure region? (e.g., eastus, westus2)`
- Save as: `Topic.Location`
- Default: `eastus`

**4. Call Power Automate Flow**
- Select your flow
- Map inputs:
  - `prompt` → `Topic.Prompt`
  - `location` → `Topic.Location`
- Save outputs to `Topic.Response`

**5. Condition - Check Success**
- If `Topic.Response.pr_url` is not blank → Success
- Else → Error

**6. Success Message**
```
✅ I've generated your Terraform code and created a Pull Request!

📋 Review it here: {Topic.Response.pr_url}

Next steps:
1. Review the Terraform code
2. Approve and merge the PR
3. GitHub Actions will deploy your infrastructure

Would you like to create more resources?
```

**7. Error Message**
```
❌ Sorry, I couldn't generate the Terraform code. Please try again with more details.
```

---

## Step 5: Test the Integration

### 5.1 Test in Copilot Studio

1. Open **Test copilot** panel
2. Type: `Create a storage account in eastus`
3. Answer the prompts
4. Verify PR is created

### 5.2 Example Conversation

```
User: Create a storage account with blob container

Bot: I'll help you create Azure infrastructure! Let me gather a few details.
     What Azure resources would you like to create?

User: Azure storage account with a private blob container for backups

Bot: Which Azure region? (e.g., eastus, westus2)

User: westus2

Bot: ✅ I've generated your Terraform code and created a Pull Request!

     📋 Review it here: https://github.com/gethiten/copilot-terraform-agent/pull/1

     Next steps:
     1. Review the Terraform code
     2. Approve and merge the PR
     3. GitHub Actions will deploy your infrastructure
```

---

## Step 6: Deploy to Teams (Optional)

### 6.1 Publish Copilot

1. Go to **Publish** in Copilot Studio
2. Click **Publish** to make changes live

### 6.2 Add to Teams

1. Go to **Channels** → **Microsoft Teams**
2. Click **Turn on Teams**
3. Follow the prompts to add to Teams

Users can now chat with the bot directly in Microsoft Teams!

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Prompt is required" error | Ensure prompt field is passed from Copilot |
| PR not created | Check GITHUB_TOKEN is set in App Service |
| Flow timeout | Increase Power Automate timeout |
| OpenAI errors | Verify AZURE_OPENAI_* settings |

### Debug Steps

1. Check API health: `https://your-app.azurewebsites.net/api/health`
2. View App Service logs: `az webapp log tail --name copilot-terraform-agent --resource-group rg-copilot-terraform`
3. Check Power Automate run history for detailed errors

---

## Security Recommendations

1. **API Authentication**: Add API key or Azure AD auth for production
2. **Rate Limiting**: Implement rate limits to prevent abuse
3. **PR Reviews**: Require PR approval before Terraform deployment
4. **Audit Logging**: Monitor all API requests
5. **Secrets**: Use Azure Key Vault for sensitive values

---

## Architecture Comparison

### This Project (Copilot Studio + Azure OpenAI)
```
Teams/Web → Copilot Studio → Power Automate → This API → Azure OpenAI
                                                  ↓
                                           GitHub PR → Deploy
```

### terraform-generator-app (Foundry Agent)
```
Web App → Flask API → Azure AI Foundry Agent → GPT-4o
                           ↓
                    GitHub PR → Deploy
```

**When to use which:**
- **Copilot Studio**: Teams integration, conversational UI, Power Platform users
- **Foundry Agent**: Custom web app, more control, agent features

---

## Files Reference

| File | Description |
|------|-------------|
| `app.py` | Main Flask application |
| `docs/copilot-openapi.json` | OpenAPI spec for custom connector |
| `templates/index.html` | Web test interface |
| `.env.example` | Environment variables template |
