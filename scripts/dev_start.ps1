Write-Host "Starting Multimodal Agentic WhatsApp AI Automation Platform Dev Environment..." -ForegroundColor Green

# Check if Docker is running
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Start infrastructure via docker compose
Write-Host "Starting PostgreSQL and Redis..." -ForegroundColor Cyan
docker compose up -d postgres redis

# Wait for Postgres
Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Cyan
$max_retries = 30
$retry_count = 0
$postgres_ready = $false

while (-not $postgres_ready -and $retry_count -lt $max_retries) {
    # Check if we can run a simple query using docker exec
    $result = docker exec $(docker compose ps -q postgres) pg_isready -U whatsapp_agent -d whatsapp_agent 2>&1
    if ($LASTEXITCODE -eq 0) {
        $postgres_ready = $true
        Write-Host "PostgreSQL is ready!" -ForegroundColor Green
    } else {
        $retry_count++
        Start-Sleep -Seconds 2
    }
}

if (-not $postgres_ready) {
    Write-Host "Timed out waiting for PostgreSQL." -ForegroundColor Red
    exit 1
}

# Run database migrations
Write-Host "Running Alembic migrations..." -ForegroundColor Cyan
alembic upgrade head

# Instructions for frontend
Write-Host "Database and cache are running." -ForegroundColor Green
Write-Host "To start the backend API:" -ForegroundColor Yellow
Write-Host "  uvicorn apps.api.main:app --reload" -ForegroundColor Yellow
Write-Host ""
Write-Host "To start the frontend:" -ForegroundColor Yellow
Write-Host "  cd apps/web && npm run dev" -ForegroundColor Yellow
Write-Host ""
Write-Host "To start the worker:" -ForegroundColor Yellow
Write-Host "  python -m apps.worker.main" -ForegroundColor Yellow

# Start backend (optional, uncomment to auto-start)
# Write-Host "Starting Uvicorn API server..." -ForegroundColor Cyan
# uvicorn apps.api.main:app --reload
