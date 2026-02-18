"""
Copilot Terraform Agent - Dual Mode Backend
This app provides API endpoints for:
1. Microsoft Copilot Studio agent (receives pre-generated code)
2. Web UI with Azure OpenAI (generates Terraform from prompts)
"""

import os
import json
import re
import requests
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

app = Flask(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Azure OpenAI Configuration (optional - for web UI generation)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL")
OUTPUT_DIRECTORY = os.getenv("OUTPUT_DIRECTORY", "generated_terraform")

# Initialize Azure OpenAI client (optional)
openai_client = None
if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
    openai_client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )

# =============================================================================
# TERRAFORM GENERATION PROMPT
# =============================================================================

TERRAFORM_SYSTEM_PROMPT = """You are an expert Azure Infrastructure Engineer and Terraform specialist.
Your role is to generate production-ready Terraform code for Azure resources.

## OUTPUT FORMAT
You MUST return ONLY valid Terraform code blocks. Use this exact structure:

```hcl
# providers.tf content here
```

```hcl
# variables.tf content here
```

```hcl
# main.tf content here
```

```hcl
# outputs.tf content here
```

## CRITICAL RULES
1. Always use AzureRM provider version ~> 4.0
2. Include proper variable definitions with descriptions
3. Use data sources for existing resources (never create duplicates)
4. Add meaningful outputs for created resources
5. Follow Azure naming conventions (lowercase, hyphens)
6. Include tags for resource management
7. Use locals for computed values

## PROVIDER CONFIGURATION
```hcl
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
```

## VARIABLE PATTERNS
- Always include: subscription_id, location, resource_group_name
- Use sensible defaults where appropriate
- Add validation blocks for critical variables

## RESOURCE NAMING
Use format: {prefix}-{resource_type}-{environment}
Example: tfgen-storage-prod

Generate clean, production-ready Terraform code based on the user's requirements."""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_terraform_blocks(terraform_code: str) -> dict:
    """Extract Terraform code blocks from the response."""
    blocks = {
        'providers.tf': '',
        'variables.tf': '',
        'main.tf': '',
        'outputs.tf': ''
    }
    
    # Find all HCL code blocks
    pattern = r'```(?:hcl|terraform)?\s*\n(.*?)```'
    matches = re.findall(pattern, terraform_code, re.DOTALL)
    
    if not matches:
        # If no code blocks, treat entire response as main.tf
        blocks['main.tf'] = terraform_code.strip()
        return blocks
    
    # Categorize blocks based on content
    for i, block in enumerate(matches):
        block = block.strip()
        if not block:
            continue
            
        if 'terraform {' in block or 'provider "' in block:
            blocks['providers.tf'] += block + '\n\n'
        elif 'variable "' in block:
            blocks['variables.tf'] += block + '\n\n'
        elif 'output "' in block:
            blocks['outputs.tf'] += block + '\n\n'
        else:
            blocks['main.tf'] += block + '\n\n'
    
    # Clean up
    for key in blocks:
        blocks[key] = blocks[key].strip()
    
    return blocks


def save_terraform_files(blocks: dict, prompt: str) -> str:
    """Save Terraform files to disk."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(OUTPUT_DIRECTORY) / f"terraform_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save each file
    for filename, content in blocks.items():
        if content:
            file_path = output_dir / filename
            with open(file_path, 'w') as f:
                f.write(content)
    
    # Save metadata
    metadata = {
        "prompt": prompt,
        "timestamp": timestamp,
        "files": [f for f, c in blocks.items() if c]
    }
    with open(output_dir / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Create README
    readme = f"""# Generated Terraform Configuration

## Prompt
{prompt}

## Generated Files
{chr(10).join(['- ' + f for f in metadata['files']])}

## Usage
```bash
terraform init
terraform plan
terraform apply
```

## Generated
{datetime.now().isoformat()}
"""
    with open(output_dir / "README.md", 'w') as f:
        f.write(readme)
    
    return str(output_dir)


def create_github_pr(terraform_blocks: dict, prompt: str, branch_name: str = None) -> dict:
    """Create a GitHub PR with the generated Terraform code."""
    if not GITHUB_TOKEN or not GITHUB_REPO_URL:
        return {"error": "GitHub not configured"}
    
    # Parse repo info
    match = re.match(r'https://github\.com/([^/]+)/([^/\.]+)', GITHUB_REPO_URL)
    if not match:
        return {"error": "Invalid GitHub repo URL"}
    
    owner, repo = match.groups()
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # Get default branch SHA
        ref_response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/main",
            headers=headers
        )
        if ref_response.status_code != 200:
            return {"error": "Failed to get main branch"}
        
        base_sha = ref_response.json()["object"]["sha"]
        
        # Create new branch
        if not branch_name:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            branch_name = f"terraform/copilot-{timestamp}"
        
        requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha}
        )
        
        # Create files in the branch
        folder_name = f"deployments/{branch_name.replace('/', '-')}"
        
        for filename, content in terraform_blocks.items():
            if content:
                file_path = f"{folder_name}/{filename}"
                requests.put(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}",
                    headers=headers,
                    json={
                        "message": f"Add {filename}",
                        "content": __import__('base64').b64encode(content.encode()).decode(),
                        "branch": branch_name
                    }
                )
        
        # Create PR
        pr_response = requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers,
            json={
                "title": f"🤖 Copilot: {prompt[:60]}{'...' if len(prompt) > 60 else ''}",
                "body": f"## Terraform Infrastructure Request\n\n**Prompt:** {prompt}\n\n---\n\n*Generated by Copilot Terraform Agent*",
                "head": branch_name,
                "base": "main"
            }
        )
        
        if pr_response.status_code == 201:
            pr_data = pr_response.json()
            return {
                "success": True,
                "pr_url": pr_data["html_url"],
                "pr_number": pr_data["number"],
                "branch_name": branch_name
            }
        else:
            return {"error": f"Failed to create PR: {pr_response.text}"}
            
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Copilot Terraform Agent",
        "version": "3.0.0",
        "description": "Dual-mode: Web UI (Azure OpenAI) + Copilot Studio",
        "azure_openai_configured": openai_client is not None,
        "github_configured": bool(GITHUB_TOKEN and GITHUB_REPO_URL)
    })


@app.route('/api/generate', methods=['POST'])
def generate_terraform():
    """
    Generate Terraform code using Azure OpenAI (for Web UI).
    
    Request Body:
    {
        "prompt": "Create a storage account with blob container",
        "location": "eastus",
        "resource_group_name": "my-rg",
        "create_pr": true
    }
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('prompt'):
            return jsonify({
                "success": False,
                "error": "Prompt is required"
            }), 400
        
        if not openai_client:
            return jsonify({
                "success": False,
                "error": "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."
            }), 500
        
        prompt = data['prompt']
        location = data.get('location', 'eastus')
        resource_group_name = data.get('resource_group_name', '')
        create_pr = data.get('create_pr', True)
        
        # Enhance prompt with context
        enhanced_prompt = f"{prompt}\n\nLocation: {location}"
        if resource_group_name:
            enhanced_prompt += f"\nResource Group: {resource_group_name}"
        
        print(f"\n{'='*60}")
        print("🤖 Azure OpenAI - Terraform Generation Request")
        print(f"{'='*60}")
        print(f"Prompt: {prompt}")
        print(f"Location: {location}")
        print(f"{'='*60}\n")
        
        # Call Azure OpenAI
        response = openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": TERRAFORM_SYSTEM_PROMPT},
                {"role": "user", "content": enhanced_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        terraform_response = response.choices[0].message.content
        
        # Parse the response into files
        terraform_blocks = parse_terraform_blocks(terraform_response)
        
        # Save to disk
        saved_path = save_terraform_files(terraform_blocks, prompt)
        print(f"💾 Saved to: {saved_path}")
        
        # Create PR if requested
        pr_result = {}
        if create_pr:
            pr_result = create_github_pr(terraform_blocks, prompt)
            if pr_result.get('success'):
                print(f"✅ PR created: {pr_result['pr_url']}")
        
        # Build response message
        if pr_result.get('success'):
            message = f"✅ Terraform code generated and PR created for review."
        else:
            message = f"✅ Terraform code generated successfully."
        
        return jsonify({
            "success": True,
            "terraform_code": terraform_response,
            "files": terraform_blocks,
            "saved_path": saved_path,
            "pr_url": pr_result.get('pr_url'),
            "pr_number": pr_result.get('pr_number'),
            "message": message
        })
        
    except Exception as e:
        print(f"⚠️ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/copilot/generate', methods=['POST'])
def copilot_generate():
    """
    Commit Terraform code to GitHub and create a PR.
    This endpoint receives Terraform code generated by Copilot Studio.
    
    Request Body:
    {
        "terraform_code": "terraform { ... }",
        "description": "Create a storage account with blob container",
        "location": "eastus",
        "create_pr": true
    }
    
    Response:
    {
        "success": true,
        "pr_url": "https://github.com/...",
        "message": "..."
    }
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('terraform_code'):
            return jsonify({
                "success": False,
                "error": "terraform_code is required. Copilot Studio should generate the Terraform code."
            }), 400
        
        terraform_code = data['terraform_code']
        description = data.get('description', 'Infrastructure deployment')
        location = data.get('location', 'eastus')
        create_pr = data.get('create_pr', True)
        
        print(f"\n{'='*60}")
        print("🤖 Copilot Studio - Commit Terraform Request")
        print(f"{'='*60}")
        print(f"Description: {description}")
        print(f"Location: {location}")
        print(f"Code length: {len(terraform_code)} chars")
        print(f"{'='*60}\n")
        
        # Parse the Terraform code into files
        terraform_blocks = parse_terraform_blocks(terraform_code)
        
        # Save to disk
        saved_path = save_terraform_files(terraform_blocks, description)
        print(f"💾 Saved to: {saved_path}")
        
        # Create PR if requested
        pr_result = {}
        if create_pr:
            pr_result = create_github_pr(terraform_blocks, description)
            if pr_result.get('success'):
                print(f"✅ PR created: {pr_result['pr_url']}")
        
        # Build response message
        if pr_result.get('success'):
            message = f"✅ Terraform code committed and PR created for review."
        else:
            message = f"✅ Terraform code saved successfully."
            if pr_result.get('error'):
                message += f" (GitHub: {pr_result['error']})"
        
        return jsonify({
            "success": True,
            "files": terraform_blocks,
            "saved_path": saved_path,
            "pr_url": pr_result.get('pr_url'),
            "pr_number": pr_result.get('pr_number'),
            "branch_name": pr_result.get('branch_name'),
            "message": message
        })
        
    except Exception as e:
        print(f"⚠️ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/copilot/status/<pr_number>', methods=['GET'])
def copilot_pr_status(pr_number):
    """
    Check the status of a PR.
    
    Response:
    {
        "pr_number": 123,
        "state": "open|closed|merged",
        "deployment_status": "pending|success|failure"
    }
    """
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO_URL:
            return jsonify({"error": "GitHub not configured"}), 500
        
        match = re.match(r'https://github\.com/([^/]+)/([^/\.]+)', GITHUB_REPO_URL)
        if not match:
            return jsonify({"error": "Invalid repo configuration"}), 500
        
        owner, repo = match.groups()
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Get PR info
        pr_response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
            headers=headers
        )
        
        if pr_response.status_code != 200:
            return jsonify({"error": "PR not found"}), 404
        
        pr_data = pr_response.json()
        state = pr_data.get('state')
        merged = pr_data.get('merged', False)
        
        if merged:
            deployment_status = "deployed"
            message = "✅ Infrastructure has been deployed."
        elif state == 'closed':
            deployment_status = "cancelled"
            message = "❌ PR was closed without merging."
        else:
            deployment_status = "pending_review"
            message = "⏳ PR is awaiting review and approval."
        
        return jsonify({
            "success": True,
            "pr_number": int(pr_number),
            "pr_url": pr_data.get('html_url'),
            "state": state,
            "merged": merged,
            "deployment_status": deployment_status,
            "message": message,
            "title": pr_data.get('title')
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/templates', methods=['GET'])
def list_templates():
    """
    List available Terraform templates.
    Useful for Copilot Studio to show options to users.
    """
    templates = [
        {
            "id": "storage",
            "name": "Storage Account",
            "description": "Azure Storage Account with blob container",
            "prompt": "Create an Azure Storage Account with a blob container"
        },
        {
            "id": "webapp",
            "name": "Web App",
            "description": "Azure App Service with App Service Plan",
            "prompt": "Create an Azure App Service with App Service Plan"
        },
        {
            "id": "function",
            "name": "Function App",
            "description": "Azure Function App with consumption plan",
            "prompt": "Create an Azure Function App with consumption plan and storage"
        },
        {
            "id": "vm",
            "name": "Virtual Machine",
            "description": "Azure Virtual Machine with networking",
            "prompt": "Create an Azure Linux Virtual Machine with VNet, subnet, and public IP"
        },
        {
            "id": "aks",
            "name": "Kubernetes Cluster",
            "description": "Azure Kubernetes Service cluster",
            "prompt": "Create an Azure Kubernetes Service cluster with 2 nodes"
        },
        {
            "id": "cosmosdb",
            "name": "Cosmos DB",
            "description": "Azure Cosmos DB account with SQL API",
            "prompt": "Create an Azure Cosmos DB account with SQL API database and container"
        }
    ]
    
    return jsonify({
        "success": True,
        "templates": templates
    })


# =============================================================================
# WEB INTERFACE
# =============================================================================

@app.route('/')
def index():
    """Simple web interface for testing."""
    return render_template('index.html')


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("="*60)
    print("🤖 Copilot Terraform Agent (Dual Mode)")
    print("="*60)
    print(f"Azure OpenAI: {'✅ Configured' if openai_client else '❌ Not configured (Web UI generation disabled)'}")
    print(f"GitHub: {'✅ Configured' if GITHUB_TOKEN else '❌ Not configured'}")
    print(f"Listening on: http://{host}:{port}")
    print("="*60)
    print("Endpoints:")
    print("  /api/generate       - Generate Terraform (Azure OpenAI)")
    print("  /api/copilot/generate - Commit Terraform (Copilot Studio)")
    print("="*60)
    
    app.run(host=host, port=port, debug=debug)
