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
  description = "The Azure Subscription ID."
  type        = string
}

variable "location" {
  description = "The Azure region to deploy resources."
  type        = string
  default     = "westus2"
}

resource "azurerm_storage_account" "testhitenst" {
  name                     = "testhitenst"
  resource_group_name      = "rg-copilot-terraform-agent"
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  allow_blob_public_access = false
}

output "storage_account_name" {
  description = "The name of the storage account."
  value       = azurerm_storage_account.testhitenst.name
}

output "storage_account_primary_endpoint" {
  description = "The primary endpoint for the storage account."
  value       = azurerm_storage_account.testhitenst.primary_blob_endpoint
}