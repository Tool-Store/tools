# Tool Store Tools
This repo is for open source tools that can be used in the Tool Store ecosystem. Please use these as examples on how to build more tools.


# Tool Store Developer Documentation

## Overview

The Tool Store is a marketplace for AI tools that integrates with the Model Context Protocol (MCP). This guide provides comprehensive documentation for developers who want to create, upload, and manage tools in the Tool Store ecosystem.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Developer API Reference](#developer-api-reference)
3. [Tool Data YAML Specification](#tool-data-yaml-specification)
4. [Tool Development Workflow](#tool-development-workflow)
5. [Tool User Data Management](#tool-user-data-management)
6. [Tool Storage System](#tool-storage-system)
7. [Tool Activation System](#tool-activation-system)
8. [Authentication & Security](#authentication--security)
9. [Examples](#examples)
10. [API Documentation Links](#api-documentation-links)

---

## Getting Started

### Prerequisites

- Firebase account for authentication
- Tool Store developer account
- Basic understanding of YAML, Python, and REST APIs
- Understanding of the Model Context Protocol (MCP)

### Development Environment Setup

1. **Authentication**: Register as a developer through the UI API
2. **API Access**: Obtain API keys for Developer API access
3. **Tool Development**: Prepare your tool code and configuration
4. **Testing**: Use the provided endpoints to test your tool integration

---

## Developer API Reference

The Developer API (`/dev_api/v1/`) provides infrastructure services that tools can access for data storage, file management, and user interactions.

### Base URL
```
https://api.toolstore.com/dev_api/v1/
```

### Core Services

#### 1. Tool User Data Management (`/tool-user-data/`)

**Purpose**: Store and manage user-specific data for your tools with support for complex nested structures.

**Collection Structure**: `{dev_slug}-{tool_slug}`
**Sub-Collection Structure**: `{dev_slug}-{tool_slug}/{user_id}/{sub_collection}`

**Key Endpoints**:
- `POST /tool-user-data/` - Create user data
- `GET /tool-user-data/{dev_slug}/{tool_slug}/user/{user_id}` - Get user data
- `PUT /tool-user-data/{dev_slug}/{tool_slug}/user/{user_id}` - Update user data
- `DELETE /tool-user-data/{dev_slug}/{tool_slug}/user/{user_id}` - Delete user data
- `POST /tool-user-data/sub-collection` - Create sub-collection document
- `GET /tool-user-data/sub-collection/{dev_slug}/{tool_slug}/{user_id}/{sub_collection}` - List sub-collection documents

#### 2. Tool Storage (`/tool-storage/`)

**Purpose**: Store and manage files for your tools with Google Cloud Storage integration.

**Storage Structure**: `/{dev_slug}-{tool_slug}/{user_slug}/{file_name}`

**Key Endpoints**:
- `POST /tool-storage/upload` - Direct file upload
- `POST /tool-storage/generate-upload-url` - Generate presigned upload URL
- `GET /tool-storage/download/{dev_slug}/{tool_slug}/{user_slug}/{file_name}` - Download file
- `GET /tool-storage/list/{dev_slug}/{tool_slug}/{user_slug}` - List user files
- `DELETE /tool-storage/delete/{dev_slug}/{tool_slug}/{user_slug}/{file_name}` - Delete file

### Authentication

All Developer API endpoints require Firebase authentication with JWT tokens:

```http
Authorization: Bearer {your_jwt_token}
```

---

## Tool Data YAML Specification

The `tool-data.yaml` file is the heart of your tool configuration. It defines metadata, capabilities, activation steps, and integration details.

### Complete YAML Schema

```yaml
# Tool Metadata
name: "My Awesome Tool"
slug: "my-awesome-tool"
short_description: "Quick data analysis and visualization"
long_description: "A comprehensive tool for data analysis and visualization that helps users create insightful charts, generate reports, and analyze datasets with ease. Perfect for business professionals and analysts."
version: "1.0.0"
content_rating: "everyone"  # Options: everyone, teen, mature

# Tool Categories and Tags
categories:
  - "data-analysis"
  - "visualization"
tags:
  - "analytics"
  - "charts"
  - "reporting"
  - "dashboard"

# Tool Actions
actions:
  - "Analyze datasets and generate insights"
  - "Create interactive charts and visualizations"
  - "Generate automated reports"
  - "Export data in multiple formats"

# Tool Images
tool_profile_image: "https://example.com/images/profile.png"
tool_images:
  - "https://example.com/images/screenshot1.png"
  - "https://example.com/images/screenshot2.png"
  - "https://example.com/images/demo.gif"

# Contact Information
website: "https://awesome-tool.com"
support_email: "support@awesome-tool.com"

# Pricing Configuration
pricing:
  type: "subscription"  # Options: free, one-time, subscription
  amount: 9.99
  currency: "USD"
  billing_period: "monthly"  # For subscriptions: monthly, yearly
  trial_days: 14

# Tool Capabilities (MCP Functions)
functions:
  - name: "analyze_data"
	description: "Analyze datasets and generate insights"
	parameters:
	  type: "object"
	  properties:
		dataset_url:
		  type: "string"
		  description: "URL to the dataset"
		analysis_type:
		  type: "string"
		  enum: ["basic", "advanced", "custom"]
	  required: ["dataset_url"]
	
  - name: "create_visualization"
	description: "Create charts and visualizations"
	parameters:
	  type: "object"
	  properties:
		data:
		  type: "array"
		  description: "Data to visualize"
		chart_type:
		  type: "string"
		  enum: ["bar", "line", "pie", "scatter"]
	  required: ["data", "chart_type"]

# Tool Resources (MCP Resources)
resources:
  - name: "user_reports"
	description: "Access user-generated reports"
	uri_template: "reports://{user_id}/{report_id}"
	
  - name: "shared_datasets"
	description: "Access shared datasets"
	uri_template: "datasets://shared/{dataset_id}"

# Tool Activation Configuration
activation:
  steps:
	# OAuth2 Step
	- type: "oauth2"
	  title: "1. Connect Your Account"
	  description: "Connect your Google account to access Drive files"
	  required: true
	  config:
		provider: "google"
		scopes:
		  - "https://www.googleapis.com/auth/drive.readonly"
		  - "https://www.googleapis.com/auth/spreadsheets"
		redirect_uri: "https://api.toolstore.com/oauth/callback"
	
	# Form Configuration Step
	- type: "form"
	  title: "2. Configure Settings"
	  description: "Provide additional configuration for the tool"
	  required: true
	  fields:
		- name: "workspace_id"
		  label: "Workspace ID"
		  type: "text"
		  required: true
		  placeholder: "Enter your workspace identifier"
		  description: "Your organization's workspace ID"
		  validation:
			pattern: "^[a-zA-Z0-9_-]{3,50}$"
			message: "Workspace ID must be 3-50 characters, alphanumeric, dashes, and underscores only"
		
		- name: "api_key"
		  label: "API Key"
		  type: "password"
		  required: false
		  secret: true
		  description: "Optional API key for enhanced features"
		
		- name: "notification_email"
		  label: "Notification Email"
		  type: "email"
		  required: true
		  description: "Email for receiving notifications"
		
		- name: "data_retention_days"
		  label: "Data Retention (Days)"
		  type: "number"
		  required: false
		  placeholder: "30"
		  validation:
			min: 1
			max: 365

# Environment Variables and Secrets
secrets:
  - name: "DB_CONNECTION"
	type: "connection_string"
	description: "Database connection string"
	required: true
	# optional default value for non-required secrets
	# default: "postgresql://user:pass@host:5432/db"
  
  - name: "EXTERNAL_API_SECRET"
	type: "api_key"
	description: "Third-party API secret key"
	required: false
	# default: ""

# Tool Requirements
requirements:
  python_version: ">=3.8"
  dependencies:
	- "pandas>=1.3.0"
	- "matplotlib>=3.5.0"
	- "requests>=2.25.0"
  system_requirements:
	memory: "512MB"
	storage: "100MB"
	cpu: "1 core"

# Tool Permissions
permissions:
  user_data:
	read: true
	write: true
	delete: false
  file_storage:
	upload: true
	download: true
	delete: true
  external_apis:
	- "googleapis.com"
	- "api.example.com"

# Deployment Configuration
deployment:
  entry_point: "main.py"
  build_command: "pip install -r requirements.txt"
  start_command: "python main.py"
  health_check_path: "/health"
  environment_variables:
	- "NODE_ENV=production"
	- "LOG_LEVEL=info"

# Tool Metadata for Discovery
discovery:
  featured: false
  popularity_score: 0
  compatibility:
	- "openai-gpt"
	- "anthropic-claude"
	- "google-gemini"
  use_cases:
	- "Data analysis and reporting"
	- "Business intelligence dashboards"
	- "Automated insights generation"
  target_audience:
	- "Data analysts"
	- "Business professionals"
	- "Researchers"
```

### Field Specifications

#### Metadata Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Tool display name |
| `slug` | string | Yes | Unique identifier (lowercase, hyphens) |
| `short_description` | string | Yes | Brief tool description (max 100 chars) |
| `long_description` | string | Yes | Detailed tool description |
| `version` | string | Yes | Semantic version (e.g., "1.0.0") |
| `content_rating` | string | Yes | Content rating (everyone, teen, mature) |
| `categories` | array | Yes | Tool categories for discovery |
| `tags` | array | Yes | Search tags and keywords |
| `actions` | array | Yes | List of actions the tool can perform |
| `tool_profile_image` | string | Yes | URL to main tool image |
| `tool_images` | array | Yes | URLs to screenshots and demos |
| `website` | string | No | Tool website URL |
| `support_email` | string | Yes | Support contact email |

#### Pricing Configuration

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| `type` | string | free, one-time, subscription | Pricing model |
| `amount` | number | - | Price amount |
| `currency` | string | USD, EUR, etc. | Currency code |
| `billing_period` | string | monthly, yearly | For subscriptions |
| `trial_days` | number | - | Free trial period |

#### Activation Steps

**OAuth2 Step**:
```yaml
- type: "oauth2"
  title: "Step Title"
  description: "Step description"
  required: true/false
  config:
	provider: "google" # "google" | "github" | "microsoft"
	scopes: ["scope1", "scope2"]
	redirect_uri: "optional_custom_uri"
```

**Form Step**:
```yaml
- type: "form"
  title: "Step Title"
  description: "Step description"
  required: true/false
  fields:
	- name: "field_name"
	  label: "Display Label"
	  type: "text" # "text" | "password" | "email" | "number" | "select"
	  required: true/false
	  secret: true/false  # Encrypt this field
	  placeholder: "Placeholder text"
	  description: "Help text"
	  validation:
		pattern: "regex_pattern"
		min: number
		max: number
		message: "Validation error message"
```

#### Secrets Configuration

```yaml
secrets:
  - name: "ENV_VAR_NAME"
	type: "api_key" # "api_key" | "token" | "password" | "connection_string" | "certificate" | "text" | "json" | "other"
	description: "Secret description"
	required: true/false
	# optional default value when not required
	# default: "optional_value"
```

---

## Tool Development Workflow

### 1. Initialize Tool Project

```bash
# Create tool directory structure
mkdir my-awesome-tool
cd my-awesome-tool

# Create required files
touch tool-data.yaml
touch main.py
touch requirements.txt
touch README.md
```

### 2. Configure tool-data.yaml

Create your tool configuration following the specification above.

### 3. Implement Tool Logic

```python
# main.py example
import asyncio
from mcp.server import FastMCPServer
from mcp.types import TextContent

app = FastMCPServer("my-awesome-tool")

@app.list_tools()
async def list_tools():
	return [
		{
			"name": "analyze_data",
			"description": "Analyze datasets and generate insights"
		}
	]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
	if name == "analyze_data":
		# Your tool logic here
		result = perform_analysis(arguments.get("dataset_url"))
		return TextContent(text=f"Analysis complete: {result}")

if __name__ == "__main__":
	app.run()
```

### 4. Upload Tool

Use the Developer API to upload your tool:

```bash
# Generate presigned upload URL
curl -X POST "https://api.toolstore.com/dev_api/v1/tools/generate-presigned-url" \
  -H "Authorization: Bearer {token}" \
  -d '{"dev_slug": "mydev", "tool_slug": "awesome-tool", "file_name": "tool.zip"}'

# Upload your tool zip file to the presigned URL
curl -X PUT "{presigned_url}" --upload-file tool.zip

# Process the uploaded tool
curl -X POST "https://api.toolstore.com/dev_api/v1/tools/upload-complete" \
  -H "Authorization: Bearer {token}" \
  -d '{"dev_slug": "mydev", "tool_slug": "awesome-tool", "file_path": "tool.zip"}'
```

### 5. Save Tool Metadata

```bash
curl -X POST "https://api.toolstore.com/dev_api/v1/tools/save-tool-metadata" \
  -H "Authorization: Bearer {token}" \
  -d '{
	"dev_slug": "mydev",
	"tool_slug": "awesome-tool",
	"metadata": { /* parsed tool-data.yaml content */ }
  }'
```

---

## Tool User Data Management

### Basic Data Operations

**Store User Preferences**:
```bash
curl -X POST "https://api.toolstore.com/dev_api/v1/tool-user-data/" \
  -H "Authorization: Bearer {token}" \
  -d '{
	"dev_slug": "mydev",
	"tool_slug": "awesome-tool",
	"user_id": "user123",
	"data": {
	  "preferences": {
		"theme": "dark",
		"notifications": true
	  }
	}
  }'
```

### Sub-Collections for Complex Data

**Create User Notes**:
```bash
curl -X POST "https://api.toolstore.com/dev_api/v1/tool-user-data/sub-collection" \
  -H "Authorization: Bearer {token}" \
  -d '{
	"dev_slug": "mydev",
	"tool_slug": "awesome-tool",
	"user_id": "user123",
	"sub_collection": "notes",
	"data": {
	  "title": "Meeting Notes",
	  "content": "Discussion about Q4 targets",
	  "created_at": "2025-07-18T10:30:00Z"
	},
	"document_id": "note_001"
  }'
```

**List User Notes**:
```bash
curl -X GET "https://api.toolstore.com/dev_api/v1/tool-user-data/sub-collection/mydev/awesome-tool/user123/notes" \
  -H "Authorization: Bearer {token}"
```

---

## Tool Storage System

### File Upload

**Direct Upload**:
```bash
curl -X POST "https://api.toolstore.com/dev_api/v1/tool-storage/upload" \
  -H "Authorization: Bearer {token}" \
  -F "dev_slug=mydev" \
  -F "tool_slug=awesome-tool" \
  -F "user_slug=user123" \
  -F "file_name=reports/quarterly-report.pdf" \
  -F "file=@quarterly-report.pdf"
```

**Presigned URL Upload**:
```bash
# Get presigned URL
curl -X POST "https://api.toolstore.com/dev_api/v1/tool-storage/generate-upload-url" \
  -H "Authorization: Bearer {token}" \
  -d '{
	"dev_slug": "mydev",
	"tool_slug": "awesome-tool",
	"user_slug": "user123",
	"file_name": "images/chart.png",
	"content_type": "image/png"
  }'

# Upload to presigned URL
curl -X PUT "{presigned_url}" --upload-file chart.png
```

### File Management

**List Files**:
```bash
curl -X GET "https://api.toolstore.com/dev_api/v1/tool-storage/list/mydev/awesome-tool/user123?prefix=reports/" \
  -H "Authorization: Bearer {token}"
```

**Download File**:
```bash
curl -X GET "https://api.toolstore.com/dev_api/v1/tool-storage/download/mydev/awesome-tool/user123/reports/quarterly-report.pdf" \
  -H "Authorization: Bearer {token}"
```

---

## Tool Activation System

The activation system provides a wizard-like interface for users to configure your tool.

### Configuration Endpoint

When users start activating your tool, the system reads your `tool-data.yaml` activation configuration:

```bash
curl -X GET "https://api.toolstore.com/ui_api/v1/tools/mydev-awesome-tool/activation-config" \
  -H "Authorization: Bearer {token}"
```

This returns the activation steps defined in your YAML file and changes the tool status to "activating".

### OAuth Callback

For OAuth steps, the system handles the callback automatically:

```
GET /ui_api/v1/tools/auth/callback/mydev-awesome-tool/user123/google?code={auth_code}
```

### Form Data Submission

Users submit form data for each step:

```bash
curl -X POST "https://api.toolstore.com/ui_api/v1/tools/mydev-awesome-tool/activation" \
  -H "Authorization: Bearer {token}" \
  -d '{
	"step_index": 1,
	"step_type": "form",
	"data": {
	  "workspace_id": "company_workspace",
	  "notification_email": "user@example.com",
	  "api_key": "secret_key_123"
	}
  }'
```

### Activation Status

Check activation progress:

```bash
curl -X GET "https://api.toolstore.com/ui_api/v1/tools/mydev-awesome-tool/activation-status" \
  -H "Authorization: Bearer {token}"
```

---

## Authentication & Security

### API Authentication

All API calls require Firebase authentication:

1. **Obtain Firebase ID Token**: Use Firebase SDK in your application
2. **Exchange for API Token**: Call the auth endpoints to get API access token
3. **Include in Requests**: Add `Authorization: Bearer {token}` header

### Security Best Practices

1. **Secret Fields**: Mark sensitive form fields as `secret: true` in your YAML
2. **OAuth Tokens**: Automatically encrypted when stored
3. **API Keys**: Store in secrets configuration, not in code
4. **Validation**: Use validation rules in form fields
5. **Permissions**: Define minimal required permissions

### Data Encryption

- OAuth tokens: Automatically encrypted using Fernet encryption
- Secret form fields: Encrypted when `secret: true` is specified
- Environment variables: Securely managed through secrets system

---

## Examples

### Example 1: Simple Analytics Tool

```yaml
name: "Data Insights Pro"
slug: "data-insights-pro"
short_description: "Automated data analysis and reporting"
long_description: "Generate comprehensive data reports and insights automatically. Perfect for business analysts who need quick data analysis without complex setup."
version: "1.0.0"
content_rating: "everyone"
categories:
  - "data-analysis"
  - "business-intelligence"
tags:
  - "analytics"
  - "reporting"
  - "automation"
actions:
  - "generate report"
  - "create automated insights"
  - "export analysis results"
tool_profile_image: "https://example.com/data-insights-pro.png"
tool_images:
  - "https://example.com/dashboard-screenshot.png"
  - "https://example.com/report-demo.gif"
website: "https://datainsightspro.com"
support_email: "support@datainsightspro.com"

pricing:
  type: "subscription"
  amount: 29.99
  currency: "USD"
  billing_period: "monthly"

functions:
  - name: "generate_report"
	description: "Generate comprehensive data reports"
	parameters:
	  type: "object"
	  properties:
		data_source:
		  type: "string"
		  description: "Data source URL or identifier"
	  required: ["data_source"]

activation:
  steps:
	- type: "form"
	  title: "Configure Data Source"
	  fields:
		- name: "database_url"
		  label: "Database Connection"
		  type: "password"
		  secret: true
		  required: true
```

### Example 2: Social Media Tool with OAuth

```yaml
name: "Social Media Manager"
slug: "social-media-manager"
short_description: "Manage multiple social media accounts"
long_description: "Streamline your social media presence by managing multiple accounts, scheduling posts, and analyzing engagement metrics all in one place."
version: "2.1.0"
content_rating: "everyone"
categories:
  - "marketing"
  - "social-media"
tags:
  - "social-media"
  - "scheduling"
  - "analytics"
  - "marketing"
actions:
  - "Schedule posts across platforms"
  - "Analyze engagement metrics"
  - "Manage multiple accounts"
  - "Generate social media reports"
tool_profile_image: "https://example.com/social-manager.png"
tool_images:
  - "https://example.com/dashboard.png"
  - "https://example.com/scheduling.png"
  - "https://example.com/analytics.png"
website: "https://socialmediamanager.com"
support_email: "help@socialmediamanager.com"

activation:
  steps:
	- type: "oauth2"
	  title: "Connect Twitter"
	  config:
		provider: "twitter"
		scopes: ["read", "write"]
	
	- type: "oauth2"
	  title: "Connect LinkedIn"
	  config:
		provider: "linkedin"
		scopes: ["r_liteprofile", "w_member_social"]
	
	- type: "form"
	  title: "Set Posting Schedule"
	  fields:
		- name: "timezone"
		  label: "Timezone"
		  type: "select"
		  required: true
		  options:
			- "America/New_York"
			- "Europe/London"
			- "Asia/Tokyo"
```

---

## API Documentation Links

### Developer API Documentation
- **Interactive API Docs**: `https://api.toolstore.com/dev_api/docs`
- **OpenAPI Specification**: `https://api.toolstore.com/dev_api/openapi.json`

### UI API Documentation  
- **Interactive API Docs**: `https://api.toolstore.com/ui_api/docs`
- **OpenAPI Specification**: `https://api.toolstore.com/ui_api/openapi.json`

### MCP API Documentation
- **Interactive API Docs**: `https://api.toolstore.com/mcp_api/docs`
- **OpenAPI Specification**: `https://api.toolstore.com/mcp_api/openapi.json`

### Health Check Endpoints
- **Developer API**: `GET /dev_api/v1/health`
- **Tool User Data**: `GET /dev_api/v1/tool-user-data/health`
- **Tool Storage**: `GET /dev_api/v1/tool-storage/health`
- **Tool Activation**: `GET /ui_api/v1/tools/health`

---

## Support and Resources

### Community Resources
- **Developer Forum**: Join our community discussions
- **GitHub Repository**: Contribute to the Tool Store ecosystem
- **Example Tools**: Browse open-source tool examples

### Getting Help
- **Documentation Issues**: Report documentation problems
- **API Support**: Contact technical support for API issues
- **Tool Review**: Get help with tool submission and review process

### Best Practices
- Follow semantic versioning for tool updates
- Include comprehensive tool documentation
- Test activation flows thoroughly
- Implement proper error handling
- Use descriptive function and resource names
- Optimize for performance and user experience

---

## Changelog

### Latest Updates
- **Sub-collection Support**: Enhanced user data storage with nested collections
- **Tool Storage**: File management system with Google Cloud Storage
- **Multistep Activation**: YAML-driven activation workflows
- **Enhanced Security**: Improved encryption for secrets and tokens
- **Better Documentation**: Comprehensive API documentation and examples

---

*This documentation is continuously updated. For the latest information, refer to the interactive API documentation and community resources.*