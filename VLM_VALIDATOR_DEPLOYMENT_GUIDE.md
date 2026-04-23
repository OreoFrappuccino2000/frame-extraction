# VLM Validator Service Deployment Guide

## Overview

This guide explains how to deploy the VLM Validator Plugin as an HTTP service on Render.com for testing before sending to development team.

## Files Created

- `vlm_validator_service.py` - Flask HTTP wrapper for VLM validator
- `render-vlm-validator.yaml` - Render.com deployment configuration
- `requirements-service.txt` - Service dependencies
- `test_http_endpoint.py` - HTTP endpoint testing script

## Local Testing

### 1. Install Dependencies
```bash
pip install -r requirements-service.txt
```

### 2. Start Service Locally
```bash
python vlm_validator_service.py
```

### 3. Test Endpoints
```bash
python test_http_endpoint.py
```

## Render.com Deployment

### 1. Connect GitHub Repository
- Go to Render.com dashboard
- Click "New +" → "Web Service"
- Connect your GitHub repository
- Select the repository containing this code

### 2. Configure Service
- **Name**: `vlm-validator-service`
- **Region**: `Oregon` (or your preferred region)
- **Branch**: `main`
- **Root Directory**: (leave empty)
- **Build Command**: `pip install -r requirements-service.txt`
- **Start Command**: `python vlm_validator_service.py`

### 3. Environment Variables
- `PYTHON_VERSION`: `3.11.0`
- `PORT`: `5000`

### 4. Health Check
- **Path**: `/health`
- **Auto-deploy**: Enabled

## API Endpoints

### Health Check
```http
GET /health
```
Response:
```json
{
  "status": "healthy",
  "service": "vlm_validator",
  "version": "1.0.0"
}
```

### Service Information
```http
GET /info
```
Response:
```json
{
  "name": "VLM Validator Service",
  "description": "HTTP wrapper for VLM Validator Plugin",
  "endpoints": [...]
}
```

### VLM Validation
```http
POST /validate
```
Request Body:
```json
{
  "vlm_output": {
    "events": [...],
    "views": [...],
    "metrics": [...],
    "squads": [...]
  },
  "frame_timestamps": [...],
  "skills_file": "skills.md"
}
```

Response:
```json
{
  "success": true,
  "result": {
    "events": [...],
    "views": [...],
    "metrics": [...],
    "squads": [...],
    "drift_log": [...],
    "intent_analysis": {...},
    "validation_log": {...},
    "stats": {...}
  }
}
```

## Testing Remote Deployment

After deployment, test the remote service:

```bash
python test_http_endpoint.py https://your-service-name.onrender.com
```

## Troubleshooting

### Common Issues

1. **ImportError: No module named 'vlm_validator'**
   - Ensure the `vlm_validator` directory is in the repository
   - Check Python path configuration in the service

2. **ModuleNotFoundError: 'tools.validate_vlm'**
   - Verify the `vlm_validator/tools/validate_vlm.py` file exists
   - Check file permissions and paths

3. **Service fails to start**
   - Check Render.com logs for detailed error messages
   - Verify all dependencies are in `requirements-service.txt`

4. **Health check fails**
   - Ensure the `/health` endpoint is accessible
   - Check if the service is binding to the correct port

### Logs and Monitoring

- View logs in Render.com dashboard under "Logs" tab
- Monitor service health and performance
- Set up alerts for service downtime

## Next Steps

After successful deployment:

1. Share the service URL with the development team
2. Provide API documentation and examples
3. Monitor service performance and usage
4. Plan for scaling and optimization

## Support

For issues with deployment:
- Check Render.com documentation
- Review service logs for error details
- Test locally first to isolate issues