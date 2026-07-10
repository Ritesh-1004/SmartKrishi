# SmartKrishi - IBM Cloud Deployment Guide

## ═══════════════════════════════════════════════════════════════════════════
## PREREQUISITES
## ═══════════════════════════════════════════════════════════════════════════

Before deploying, ensure you have:
- IBM Cloud account (cloud.ibm.com)
- IBM Cloud CLI installed
- Docker installed (for containerized deployment)
- Git repository with the SmartKrishi code

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 1: GET IBM CLOUD API KEY AND watsonx.ai PROJECT
## ═══════════════════════════════════════════════════════════════════════════

### 1.1 Generate IBM Cloud API Key
```
# Option A: IBM Cloud Console
# → cloud.ibm.com → Manage → Access (IAM) → API Keys → Create an IBM Cloud API key

# Option B: IBM Cloud CLI
ibmcloud iam api-key-create SmartKrishi-API-Key
```
Copy the API key — it's shown only once!

### 1.2 Create watsonx.ai Project
1. Go to: cloud.ibm.com/catalog/services/watson-machine-learning
2. Create a Watson Machine Learning service (Lite tier = free)
3. Go to: dataplatform.cloud.ibm.com
4. Create a New Project → Associate with WML service
5. Copy the Project ID from: Project → Settings → General → Project ID

### 1.3 Granite Model Access
- In your watsonx.ai project, enable IBM Granite models
- Model IDs available:
  - `ibm/granite-13b-chat-v2`   (recommended for chat)
  - `ibm/granite-3b-code-instruct`
  - `ibm/granite-20b-multilingual`

### 1.4 Configure .env File
```bash
cp .env.example .env
# Edit .env with your actual values:
IBM_CLOUD_API_KEY=your-actual-api-key
WATSONX_PROJECT_ID=your-project-id
WATSONX_URL=https://us-south.ml.cloud.ibm.com  # or eu-de, eu-gb, jp-tok
WATSONX_MODEL_ID=ibm/granite-13b-chat-v2
```

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 2: LOCAL DEVELOPMENT SETUP
## ═══════════════════════════════════════════════════════════════════════════

```bash
# Clone and setup
git clone <your-repo-url>
cd SmartKrishi

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Initialize database
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Run development server
python run.py
# → App available at: http://localhost:5000
```

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 3: DOCKER DEPLOYMENT (RECOMMENDED)
## ═══════════════════════════════════════════════════════════════════════════

```bash
# Build the Docker image
docker build -t smartkrishi:latest .

# Test locally with Docker Compose
cp .env.example .env
# Edit .env with credentials

docker-compose up -d

# Check status
docker-compose ps
docker-compose logs smartkrishi

# App runs at: http://localhost:5000
```

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 4: IBM CODE ENGINE DEPLOYMENT (Serverless Containers)
## ═══════════════════════════════════════════════════════════════════════════

IBM Code Engine is the recommended serverless deployment for SmartKrishi.

### 4.1 Install IBM Cloud CLI + Code Engine Plugin
```bash
# Install IBM Cloud CLI
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh  # Linux
# Or download from: cloud.ibm.com/docs/cli

# Install Code Engine plugin
ibmcloud plugin install code-engine

# Login
ibmcloud login --apikey $IBM_CLOUD_API_KEY -r us-south
```

### 4.2 Push Image to IBM Container Registry
```bash
# Install container-registry plugin
ibmcloud plugin install container-registry

# Login to registry
ibmcloud cr login
ibmcloud cr region-set us-south

# Create namespace
ibmcloud cr namespace-add smartkrishi-ns

# Build and push
docker build -t us.icr.io/smartkrishi-ns/smartkrishi:v1 .
docker push us.icr.io/smartkrishi-ns/smartkrishi:v1
```

### 4.3 Create Code Engine Project and Deploy
```bash
# Create project
ibmcloud ce project create --name smartkrishi-prod
ibmcloud ce project select --name smartkrishi-prod

# Create secrets from .env
ibmcloud ce secret create --name smartkrishi-secrets \
  --from-env-file .env

# Deploy application
ibmcloud ce application create \
  --name smartkrishi-app \
  --image us.icr.io/smartkrishi-ns/smartkrishi:v1 \
  --cpu 1 \
  --memory 4G \
  --min-scale 1 \
  --max-scale 5 \
  --port 5000 \
  --env-from-secret smartkrishi-secrets \
  --registry-secret ibm-cr-secret

# Get application URL
ibmcloud ce application get --name smartkrishi-app --output url
```

### 4.4 Auto-Deploy on Code Push (CI/CD)
```bash
# Create a build from source repo
ibmcloud ce build create \
  --name smartkrishi-build \
  --source https://github.com/your-org/SmartKrishi \
  --strategy dockerfile \
  --image us.icr.io/smartkrishi-ns/smartkrishi:latest \
  --size medium

# Run build
ibmcloud ce buildrun submit --build smartkrishi-build

# Update app to latest image
ibmcloud ce application update --name smartkrishi-app \
  --image us.icr.io/smartkrishi-ns/smartkrishi:latest
```

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 5: IBM CLOUD FOUNDRY DEPLOYMENT (Alternative)
## ═══════════════════════════════════════════════════════════════════════════

```bash
# Install CF plugin
ibmcloud cf install

# Target org and space
ibmcloud target --cf
ibmcloud target -o "your-org" -s "dev"

# Create manifest.yml (see below)
# Deploy
ibmcloud cf push smartkrishi --no-start

# Set environment variables
ibmcloud cf set-env smartkrishi IBM_CLOUD_API_KEY "your-key"
ibmcloud cf set-env smartkrishi WATSONX_PROJECT_ID "your-project-id"
ibmcloud cf set-env smartkrishi SECRET_KEY "$(python -c 'import secrets; print(secrets.token_hex(32))')"

# Start app
ibmcloud cf start smartkrishi
```

**manifest.yml for Cloud Foundry:**
```yaml
applications:
  - name: smartkrishi
    memory: 1G
    disk_quota: 2G
    instances: 2
    buildpacks:
      - python_buildpack
    command: gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 run:app
    env:
      FLASK_ENV: production
      PYTHONUNBUFFERED: "1"
    services:
      - smartkrishi-db
      - smartkrishi-redis
```

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 6: PRODUCTION DATABASE SETUP
## ═══════════════════════════════════════════════════════════════════════════

### IBM Databases for PostgreSQL
```bash
# Create IBM PostgreSQL service (Standard plan)
ibmcloud resource service-instance-create smartkrishi-db \
  databases-for-postgresql standard us-south

# Get credentials
ibmcloud resource service-key-create smartkrishi-db-key Administrator \
  --instance-name smartkrishi-db

# Get connection string
ibmcloud resource service-key smartkrishi-db-key
# → Set DATABASE_URL in your .env
```

### IBM Databases for Redis (for caching)
```bash
ibmcloud resource service-instance-create smartkrishi-redis \
  databases-for-redis standard us-south
```

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 7: MONITORING AND LOGGING
## ═══════════════════════════════════════════════════════════════════════════

```bash
# IBM Log Analysis (LogDNA)
ibmcloud resource service-instance-create smartkrishi-logs \
  logdnaat lite us-south

# View logs
ibmcloud ce application logs --name smartkrishi-app --follow

# IBM Cloud Monitoring (Sysdig)
ibmcloud resource service-instance-create smartkrishi-monitor \
  sysdig-monitor lite us-south
```

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 8: CUSTOM DOMAIN + SSL
## ═══════════════════════════════════════════════════════════════════════════

```bash
# Map custom domain in Code Engine
ibmcloud ce application create --name smartkrishi-app \
  --registry-secret ibm-cr-secret \
  --image us.icr.io/smartkrishi-ns/smartkrishi:latest \
  --port 5000 \
  --env-from-secret smartkrishi-secrets

# IBM Certificate Manager for SSL
ibmcloud resource service-instance-create smartkrishi-certs \
  cloudcerts free us-south

# Upload/order SSL certificate via IBM Cloud dashboard
```

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 9: ENVIRONMENT VARIABLES REFERENCE
## ═══════════════════════════════════════════════════════════════════════════

| Variable                | Required | Description                              |
|-------------------------|----------|------------------------------------------|
| IBM_CLOUD_API_KEY       | YES      | IBM Cloud IAM API Key                   |
| WATSONX_PROJECT_ID      | YES      | watsonx.ai Project ID                   |
| WATSONX_URL             | YES      | Regional URL (us-south, eu-de, etc.)    |
| WATSONX_MODEL_ID        | YES      | Granite model ID                         |
| SECRET_KEY              | YES      | Flask session secret (random 32-char)   |
| DATABASE_URL            | YES      | PostgreSQL connection string            |
| WEATHER_API_KEY         | NO       | OpenWeatherMap API key (free tier OK)   |
| MANDI_API_KEY           | NO       | data.gov.in API key (free registration) |
| REDIS_URL               | NO       | Redis connection URL (for caching)      |
| TRANSLATE_API_KEY       | NO       | LibreTranslate API key                  |

---

## ═══════════════════════════════════════════════════════════════════════════
## STEP 10: USEFUL IBM CLOUD URLS
## ═══════════════════════════════════════════════════════════════════════════

- IBM Cloud Console: https://cloud.ibm.com
- watsonx.ai: https://dataplatform.cloud.ibm.com
- Code Engine: https://cloud.ibm.com/codeengine
- Container Registry: https://cloud.ibm.com/registry
- Documentation: https://cloud.ibm.com/docs
- IBM Granite Models: https://www.ibm.com/products/watsonx-ai/foundation-models
- Free Tier limits: https://cloud.ibm.com/docs/overview?topic=overview-free-tier

---

## ═══════════════════════════════════════════════════════════════════════════
## QUICK CHECKLIST
## ═══════════════════════════════════════════════════════════════════════════

- [ ] IBM Cloud account created
- [ ] IBM Cloud API Key generated and stored in .env
- [ ] watsonx.ai project created
- [ ] Project ID added to .env
- [ ] Granite model enabled in watsonx.ai project
- [ ] .env file configured (never commit this file!)
- [ ] Database created and DATABASE_URL set
- [ ] Application deployed and health check passing (/health)
- [ ] Custom domain configured (optional)
- [ ] SSL certificate attached (optional)
- [ ] Monitoring and logging enabled
