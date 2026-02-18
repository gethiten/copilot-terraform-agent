terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" { type = string }
variable "location" { type = string, default = "eastus" }

resource "azurerm_resource_group" "main" {
  name     = "rg-storage-demo"
  location = var.location
}

resource "azurerm_storage_account" "main" {
  name                     = "stdemoaccount"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}