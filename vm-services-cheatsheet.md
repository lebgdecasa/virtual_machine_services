# 🚀 VM Services Management Cheat Sheet

## 📡 Accessing Your VM

```bash
# SSH into VM
gcloud compute ssh instance-20250930-090801 --zone us-central1-c

# Get VM external IP
curl ifconfig.me
# Or
gcloud compute instances describe instance-20250930-090801 --zone us-central1-c --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

## 🐳 Docker Management

### Status & Health Checks
```bash
# Check all services status
sudo docker-compose ps

# Check specific service
sudo docker ps | grep back-service

# Inspect container details
sudo docker inspect back-service | grep -A5 "State"

# Check what's listening inside container
sudo docker exec back-service netstat -tulpn | grep LISTEN
```

### Starting/Stopping Services
```bash
# Start all services
sudo docker-compose up -d

# Stop all services
sudo docker-compose down

# Restart specific service
sudo docker-compose restart back
sudo docker-compose restart dip-risearch
sudo docker-compose restart watercrawl

# Restart all services
sudo docker-compose restart
```

### Rebuilding Services
```bash
# Rebuild single service
sudo docker-compose build back
sudo docker-compose build dip-risearch
sudo docker-compose build watercrawl

# Rebuild without cache (clean build)
sudo docker-compose build --no-cache dip-risearch

# Rebuild and restart in one command
sudo docker-compose up -d --build --force-recreate dip-risearch

# Full rebuild all services
sudo docker-compose down
sudo docker-compose build --no-cache
sudo docker-compose up -d
```

## 📋 Viewing Logs

### Real-time Streaming
```bash
# Stream logs for specific service
sudo docker-compose logs -f back
sudo docker-compose logs -f dip-risearch
sudo docker-compose logs -f watercrawl

# Stream with timestamps
sudo docker-compose logs -f --timestamps back

# Stream last 50 lines then follow
sudo docker-compose logs --tail=50 -f back

# Stream all services
sudo docker-compose logs -f
```

### Filtering Logs
```bash
# Check for errors
sudo docker-compose logs back | grep -i error
sudo docker-compose logs dip-risearch | grep -i error

# Live stream with error filter
sudo docker-compose logs -f back | grep -E "(ERROR|WARNING|Failed)"

# Check last 100 lines
sudo docker-compose logs --tail=100 back
```

## 🔄 Updating Code & Redeploying

### Quick Update Single Service
```bash
# Pull latest code
cd ~/virtual_machine_services
git pull origin main

# Rebuild and redeploy specific service
sudo docker-compose build dip-risearch
sudo docker-compose up -d --force-recreate dip-risearch

# Check it worked
sudo docker-compose ps
sudo docker-compose logs dip-risearch --tail=20
```

### Full Redeploy
```bash
cd ~/virtual_machine_services
git pull origin main
sudo docker-compose down
sudo docker-compose build --no-cache
sudo docker-compose up -d
```

### Update Script for Deep Research
```bash
#!/bin/bash
# Save as ~/update_dip_risearch.sh
echo "Updating dip-risearch service..."
cd ~/virtual_machine_services
git pull origin main
sudo docker-compose build dip-risearch
sudo docker-compose up -d --force-recreate dip-risearch
echo "Service status:"
sudo docker-compose ps dip-risearch
echo "Recent logs:"
sudo docker-compose logs dip-risearch --tail=20
```

## 🧪 Testing Endpoints

### Local Tests (from VM)
```bash
# Test health/docs
curl http://localhost:8001/docs
curl http://localhost:8002/health
curl http://localhost:8003/docs

# Test back service
curl -X POST http://localhost:8001/start_analysis \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Test dip-risearch
curl -X POST http://localhost:8002/api/research \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "depth": 1, "breadth": 1}'

# Test watercrawl
curl -X POST http://localhost:8003/search \
  -H "Content-Type: application/json" \
  -d '{"query": ["test"], "n": 3}'
```

### External Tests
```bash
# External IP: 34.57.8.144
curl http://34.57.8.144/health
curl http://34.57.8.144/start_analysis
curl http://34.57.8.144/api/research
curl http://34.57.8.144/search
```

## 🌍 Available External Endpoints

| Endpoint | Method | Service | Port | Description |
|----------|---------|---------|------|-------------|
| `/start_analysis` | POST | back-service | 8001 | Start analysis task (15 min timeout) |
| `/check_description_completeness` | POST | back-service | 8001 | Check description completeness |
| `/api/research` | POST | dip-risearch | 8002 | Deep research (15 min timeout) |
| `/search` | POST | watercrawl | 8003 | Web search (2 min timeout) |

## ⚙️ Configuration Files

### Edit Environment Variables
```bash
# Edit service environment files
nano ~/virtual_machine_services/back/.env
nano ~/virtual_machine_services/dip-risearch/.env.local
nano ~/virtual_machine_services/watercrawl/.env

# After editing, restart the service
sudo docker-compose restart back
sudo docker-compose restart dip-risearch
sudo docker-compose restart watercrawl
```

### Edit Docker Compose
```bash
nano ~/virtual_machine_services/docker-compose.yml
# After editing, recreate services
sudo docker-compose up -d
```

## 🌐 Nginx Management

### Check & Restart Nginx
```bash
# Test nginx configuration
sudo nginx -t

# Reload nginx (after config changes)
sudo systemctl reload nginx

# Restart nginx
sudo systemctl restart nginx

# Check nginx status
sudo systemctl status nginx
```

### Edit Nginx Configuration
```bash
# Edit configuration
sudo nano /etc/nginx/sites-available/api-services

# After editing, test and reload
sudo nginx -t && sudo systemctl reload nginx

# View nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### View All Endpoints
```bash
# List all configured locations
grep "location" /etc/nginx/sites-available/api-services

# View full config
cat /etc/nginx/sites-available/api-services
```

## 🔍 Debugging Commands

### Container Shell Access
```bash
# Enter container shell
sudo docker exec -it back-service /bin/bash
sudo docker exec -it dip-risearch-service /bin/sh
sudo docker exec -it watercrawl-service /bin/bash

# Check environment variables inside container
sudo docker exec back-service env | grep GEMINI
sudo docker exec dip-risearch-service env | grep OPENAI
```

### Port & Network Checks
```bash
# Check what's listening on ports
sudo netstat -tulpn | grep LISTEN

# Check if port is accessible
curl -I http://localhost:8001
curl -I http://localhost:8002
curl -I http://localhost:8003

# Check Docker networks
sudo docker network ls
sudo docker network inspect virtual_machine_services_app-network
```

### Resource Usage
```bash
# Check disk space
df -h

# Check memory
free -h

# Check Docker resource usage
sudo docker stats

# Check container resource limits
sudo docker inspect back-service | grep -A 10 "HostConfig"
```

## 🚨 Emergency Commands

### If Services Won't Start
```bash
# Check Docker daemon
sudo systemctl status docker
sudo systemctl restart docker

# Clean up Docker
sudo docker system prune -a  # Careful: removes all unused images
sudo docker-compose down -v  # Remove volumes too

# Force recreate
sudo docker-compose up -d --force-recreate
```

### If Out of Space
```bash
# Check space
df -h

# Clean Docker
sudo docker system prune -a
sudo docker volume prune

# Clear logs
sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### Check What Changed
```bash
# See git status
cd ~/virtual_machine_services
git status
git diff

# Check recent commits
git log --oneline -10
```

## 🔐 Firewall & Security

```bash
# Check firewall rules
gcloud compute firewall-rules list --filter="targetTags.list():api-server"

# Check VM tags
gcloud compute instances describe instance-20250930-090801 \
  --zone us-central1-c --format="get(tags.items)"

# Add firewall rule
gcloud compute firewall-rules create allow-api-services \
  --allow tcp:80 \
  --source-ranges 0.0.0.0/0 \
  --target-tags api-server \
  --description "Allow HTTP traffic for API services"

# Add tag to VM
gcloud compute instances add-tags instance-20250930-090801 \
  --tags=api-server \
  --zone=us-central1-c
```

## 📝 Quick Verification Script

```bash
#!/bin/bash
# Save as ~/check_all.sh
echo "=== Docker Services ==="
sudo docker-compose ps
echo -e "\n=== Port Checks ==="
for port in 8001 8002 8003; do
    curl -s -o /dev/null -w "Port $port: %{http_code}\n" http://localhost:$port
done
echo -e "\n=== Recent Errors ==="
sudo docker-compose logs --tail=10 | grep -i error || echo "No recent errors"
```

## ⏱️ Timeout Configuration

### Current nginx Timeouts
- `/start_analysis`: 15 minutes (calls research internally)
- `/api/research`: 15 minutes (long research tasks)
- `/check_description_completeness`: 60 seconds (quick checks)
- `/search`: 2 minutes (web searches)

### Update Timeouts in nginx
```nginx
location /api/research {
    # ... other config ...
    proxy_connect_timeout 900s;  # 15 minutes
    proxy_send_timeout 900s;
    proxy_read_timeout 900s;
    send_timeout 900s;
}
```

## 📊 Monitoring

### Watch Multiple Services (tmux)
```bash
# Install tmux
sudo apt-get install -y tmux

# Start session
tmux new -s logs

# Split screen: Ctrl+B then %
# Switch panes: Ctrl+B then arrow keys
# Detach: Ctrl+B then d
# Reattach: tmux attach -t logs
```

### Service Health Dashboard
```bash
#!/bin/bash
while true; do
    clear
    echo "=== Service Health Dashboard ==="
    date
    echo "--------------------------------"
    sudo docker-compose ps
    echo "--------------------------------"
    echo "Recent Errors:"
    sudo docker-compose logs --tail=5 | grep -i error || echo "None"
    sleep 5
done
```

## 🎯 Most Common Commands

```bash
# Watch logs
sudo docker-compose logs -f [service]

# Restart after changes
sudo docker-compose restart [service]

# Check status
sudo docker-compose ps

# Rebuild and restart
sudo docker-compose up -d --build --force-recreate [service]

# Test endpoint
curl -X POST http://34.57.8.144/[endpoint] -H "Content-Type: application/json" -d '{}'
```

---

**VM Details:**
- **Instance**: instance-20250930-090801
- **Zone**: us-central1-c
- **External IP**: 34.57.8.144
- **Project**: nextraction

**Services:**
- **back-service**: Port 8001 (FastAPI - Backend)
- **dip-risearch-service**: Port 8002 (Node.js - Deep Research)
- **watercrawl-service**: Port 8003 (FastAPI - Web Crawler)

---

*Last Updated: September 2025*