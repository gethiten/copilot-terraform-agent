terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "subscription_id" {
  description = "The Azure subscription ID"
  type        = string
}

variable "location" {
  description = "The Azure region to deploy resources"
  type        = string
  default     = "eastus"
}

resource "azurerm_storage_account" "test_copilot_hit_st" {
  name                     = "testcopilothitst"
  resource_group_name      = "rg-copilot-terraform-agent"
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

output "storage_account_name" {
  description = "The name of the storage account"
  value       = azurerm_storage_account.test_copilot_hit_st.name
}

output "storage_account_id" {
  description = "The ID of the storage account"
  value       = azurerm_storage_account.test_copilot_hit_st.id
}