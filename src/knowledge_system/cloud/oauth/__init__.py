"""
OAuth integration package for GetReceipts.org

This package provides complete OAuth authentication and data upload
capabilities for uploading Knowledge_Chipper HCE data to GetReceipts.org.
"""

from .getreceipts_auth import GetReceiptsAuth
from .getreceipts_uploader import GetReceiptsUploader
from .getreceipts_config import get_config, set_production, set_development
from .integration_example import upload_to_getreceipts

__all__ = [
    'GetReceiptsAuth',
    'GetReceiptsUploader', 
    'get_config',
    'set_production',
    'set_development',
    'upload_to_getreceipts'
]
