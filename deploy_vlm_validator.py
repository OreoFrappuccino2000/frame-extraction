#!/usr/bin/env python3
"""
VLM Validator Service Deployment Script

This script automates the deployment process for the VLM Validator service.
It provides step-by-step guidance for local testing and Render.com deployment.
"""

import os
import sys
import subprocess
import json
import requests
import time

def check_dependencies():
    """Check if required dependencies are installed"""
    print("Checking dependencies...")
    
    required_packages = ["Flask", "flask-cors", "requests"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.lower().replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing packages: {', '.join(missing_packages)}")
        print("Installing dependencies...")
        
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-service.txt"], 
                         check=True)
            print("✓ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install dependencies: {e}")
            return False
    else:
        print("✓ All dependencies are installed")
    
    return True

def start_local_service():
    """Start the VLM validator service locally"""
    print("\nStarting local service...")
    
    # Check if service is already running
    try:
        response = requests.get("http://localhost:5000/health", timeout=2)
        if response.status_code == 200:
            print("✓ Service is already running on localhost:5000")
            return True
    except:
        pass
    
    # Start the service
    try:
        import threading
        import vlm_validator_service
        
        def run_service():
            vlm_validator_service.app.run(host='0.0.0.0', port=5000, debug=False)
        
        service_thread = threading.Thread(target=run_service, daemon=True)
        service_thread.start()
        
        # Wait for service to start
        for i in range(10):
            try:
                response = requests.get("http://localhost:5000/health", timeout=1)
                if response.status_code == 200:
                    print("✓ Service started successfully on localhost:5000")
                    return True
            except:
                time.sleep(0.5)
        
        print("✗ Service failed to start within 5 seconds")
        return False
        
    except Exception as e:
        print(f"✗ Failed to start service: {e}")
        return False

def test_local_endpoints():
    """Test all service endpoints locally"""
    print("\nTesting local endpoints...")
    
    try:
        # Run the test script
        result = subprocess.run([sys.executable, "test_http_endpoint.py"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ All local tests passed")
            print(result.stdout)
            return True
        else:
            print("✗ Local tests failed")
            print(result.stdout)
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"✗ Test execution failed: {e}")
        return False

def check_git_status():
    """Check Git repository status"""
    print("\nChecking Git status...")
    
    try:
        # Check if we're in a git repository
        result = subprocess.run(["git", "status"], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("✗ Not in a Git repository")
            return False
        
        # Check for uncommitted changes
        result = subprocess.run(["git", "diff", "--quiet"], capture_output=True)
        if result.returncode != 0:
            print("⚠️  There are uncommitted changes")
            print("   Consider committing changes before deployment")
        else:
            print("✓ No uncommitted changes")
        
        # Check remote status
        result = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True)
        if "origin" in result.stdout:
            print("✓ Remote repository configured")
        else:
            print("⚠️  No remote repository configured")
        
        return True
        
    except Exception as e:
        print(f"✗ Git check failed: {e}")
        return False

def generate_deployment_summary():
    """Generate deployment summary"""
    print("\n" + "="*60)
    print("VLM VALIDATOR SERVICE DEPLOYMENT SUMMARY")
    print("="*60)
    
    print("\n📋 Files Ready for Deployment:")
    print("  • vlm_validator_service.py - Flask HTTP service")
    print("  • render-vlm-validator.yaml - Render.com config")
    print("  • requirements-service.txt - Dependencies")
    print("  • test_http_endpoint.py - Testing script")
    print("  • VLM_VALIDATOR_DEPLOYMENT_GUIDE.md - Full guide")
    
    print("\n🚀 Next Steps for Render.com Deployment:")
    print("  1. Push code to GitHub repository")
    print("  2. Go to Render.com dashboard")
    print("  3. Click 'New +' → 'Web Service'")
    print("  4. Connect your GitHub repository")
    print("  5. Use 'render-vlm-validator.yaml' for configuration")
    print("  6. Deploy and test the service")
    
    print("\n🔗 Service Endpoints:")
    print("  • GET /health - Health check")
    print("  • GET /info - Service information")
    print("  • POST /validate - VLM validation endpoint")
    
    print("\n📞 Testing Command:")
    print("  python test_http_endpoint.py https://your-service.onrender.com")
    
    print("\n✅ Ready for deployment!")

def main():
    """Main deployment workflow"""
    print("VLM Validator Service Deployment Script")
    print("="*50)
    
    # Step 1: Check dependencies
    if not check_dependencies():
        print("\n❌ Dependency check failed")
        return False
    
    # Step 2: Start local service
    if not start_local_service():
        print("\n❌ Failed to start local service")
        return False
    
    # Step 3: Test endpoints
    if not test_local_endpoints():
        print("\n❌ Local endpoint tests failed")
        return False
    
    # Step 4: Check Git status
    check_git_status()
    
    # Step 5: Generate summary
    generate_deployment_summary()
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🎉 Deployment preparation completed successfully!")
            sys.exit(0)
        else:
            print("\n💥 Deployment preparation failed")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Deployment script interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)