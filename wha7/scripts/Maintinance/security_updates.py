# scripts/maintenance/security_updates.py
"""Security update checker and applier."""

import subprocess
import os
from datetime import datetime

def check_security_updates():
    """Check for security updates in dependencies."""
    try:
        # Check Python dependencies
        subprocess.run(["pip", "list", "--outdated"])
        
        # Run safety check
        subprocess.run(["safety", "check"])
        
        # Check Docker base image
        subprocess.run(["docker", "images", "--format", "'{{.Repository}}:{{.Tag}}'"])
        
        # Log check completion
        with open('security_check.log', 'a') as f:
            f.write(f"Security check completed at {datetime.now()}\n")
            
    except Exception as e:
        print(f"Security check failed: {str(e)}")
        raise

def apply_updates():
    """Apply available security updates."""
    try:
        # Update Python dependencies
        subprocess.run(["pip", "install", "--upgrade", "-r", "requirements.txt"])
        
        # Update Docker images
        subprocess.run(["docker", "pull", "python:3.11-slim"])
        
        # Log update completion
        with open('security_updates.log', 'a') as f:
            f.write(f"Updates applied at {datetime.now()}\n")
            
    except Exception as e:
        print(f"Update application failed: {str(e)}")
        raise