"""
Cloudflare Services Configuration

Centralized configuration for all Cloudflare services used in the Town Market project.

Services:
- R2: Object storage (S3-compatible) for media and static files
- DNS: Domain name system management (placeholder for future)
- Workers: Serverless execution environment (placeholder for future)
- Turnstile: CAPTCHA service (placeholder for future)

Usage:
    from core.cloudflare import R2
    r2 = R2()
    url = r2.url('path/to/file')
"""

import os
from decimal import Decimal
from pathlib import Path

# ✅ Base path for any local fallbacks
BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================================
# ✅ R2 Object Storage Service
# ============================================================================

class R2:
    """
    Cloudflare R2 Configuration
    
    Provides S3-compatible object storage for media and static files.
    Uses Cloudflare's global network with built-in CDN.
    
    Example:
        >>> from core.cloudflare import R2
        >>> r2 = R2()
        >>> r2.url('product_images/logo.png')
        'https://account-id.r2.cloudflarestorage.com/bucket-name/product_images/logo.png'
    """
    
    def __init__(self):
        self.account_id = os.getenv(
            'CLOUDFLARE_R2_ACCOUNT_ID',
            default='104dbc5609bc33780236c732ecf740dd'
        )
        self.access_key_id = os.getenv(
            'CLOUDFLARE_R2_ACCESS_KEY_ID',
            default=''
        )
        self.secret_access_key = os.getenv(
            'CLOUDFLARE_R2_SECRET_ACCESS_KEY',
            default=''
        )
        self.bucket_name = os.getenv(
            'CLOUDFLARE_R2_BUCKET_NAME',
            default='townmarket'
        )
        self.endpoint = os.getenv(
            'CLOUDFLARE_R2_ENDPOINT',
            default=None  # Auto-derived from account ID
        )
        
        # ✅ Derived properties
        self.custom_domain = os.getenv(
            'CLOUDFLARE_R2_CUSTOM_DOMAIN',
            default=None
        )
        
        # ✅ Construct the base R2 URL
        if self.custom_domain:
            self.base_url = f"https://{self.custom_domain}"
        elif self.endpoint:
            self.base_url = self.endpoint
        else:
            # Auto-derived from account ID (standard R2 format)
            self.base_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
    
    @property
    def full_url(self):
        """Get the complete base URL for the R2 bucket."""
        return self.base_url
    
    def url(self, path, *, host=None):
        """
        Generate a full R2 URL for a given path.
        
        Args:
            path: Relative path within the bucket (e.g., 'product_images/logo.png')
            host: Optional custom host override
            
        Returns:
            Full URL string
        """
        # Use custom host if provided, otherwise use base URL
        base = host or self.base_url
        # Ensure path starts without leading slash
        clean_path = path.lstrip('/')
        return f"{base}/{self.bucket_name}/{clean_path}"
    
    def media_url(self, path):
        """Generate R2 URL for media files."""
        return self.url(path)
    
    def static_url(self, path):
        """Generate R2 URL for static files."""
        return self.url(path)
    
    def __repr__(self):
        return f"<R2 account={self.account_id} bucket={self.bucket_name}>"


# ✅ Global R2 instance - easy access throughout project
# Can be imported as: from core.cloudflare import r2
r2 = R2()


# ============================================================================
# ✅ Service Status Check
# ============================================================================

def is_r2_configured():
    """
    Check if R2 is properly configured with required credentials.
    
    Returns:
        bool: True if account ID and bucket name are set
    """
    return bool(
        os.getenv('CLOUDFLARE_R2_ACCOUNT_ID') and
        os.getenv('CLOUDFLARE_R2_BUCKET_NAME')
    )


def get_service_status():
    """
    Get status of all Cloudflare services.
    
    Returns:
        dict: Service configuration status
    """
    return {
        'r2_configured': is_r2_configured(),
        'r2_account_id': os.getenv('CLOUDFLARE_R2_ACCOUNT_ID', ''),
        'r2_bucket_name': os.getenv('CLOUDFLARE_R2_BUCKET_NAME', ''),
        'r2_custom_domain': os.getenv('CLOUDFLARE_R2_CUSTOM_DOMAIN', ''),
    }


# ============================================================================
# ✅ Environment Helpers
# ============================================================================

def is_production():
    """Check if running in production environment."""
    return os.getenv('ENVIRONMENT', 'development').lower() == 'production'


def is_development():
    """Check if running in development environment."""
    return not is_production()


# ✅ Default R2 instance for easy import
# Usage: from core.cloudflare import r2, is_r2_configured
r2_default = r2