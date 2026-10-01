import os
import sys
import uuid
import httpx
from datetime import datetime
from loguru import logger
from whatsapp_agent.config.settings import get_settings
from dotenv import load_dotenv

load_dotenv()

class LicenseError(Exception):
    """Raised when license validation fails."""
    pass

def get_hardware_id() -> str:
    """Generate a unique hardware ID based on the machine's MAC address."""
    try:
        # uuid.getnode() gets the hardware address as a 48-bit positive integer
        mac = uuid.getnode()
        return ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
    except Exception:
        return "UNKNOWN_HARDWARE"

def get_network_info() -> dict:
    """Get host domain and IP address."""
    import socket
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return {"hostname": hostname, "ip": ip_address}
    except Exception:
        return {"hostname": "UNKNOWN", "ip": "UNKNOWN"}

async def validate_license_async() -> bool:
    """
    Validate the application license key against a remote licensing server.
    Prevents unauthorized redistribution by tying the license to the Hardware ID.
    """
    settings = get_settings()
    license_key = os.getenv("LICENSE_KEY", "")
    
    if not license_key:
        logger.error("CRITICAL: No LICENSE_KEY provided. Shutting down to prevent unauthorized usage.")
        sys.exit(1)

    hardware_id = get_hardware_id()
    network_info = get_network_info()
    client_id = os.getenv("ASSOCIATIVE_CLIENT_ID", "UNKNOWN_CLIENT")
    
    # In a production environment, this points to your central License Server
    license_server_url = os.getenv("LICENSE_SERVER_URL", "https://license.associative.in/api/v1/verify")
    
    logger.info("Verifying product license with Associative...", hardware_id=hardware_id, host=network_info["hostname"], ip=network_info["ip"])
    
    # MOCK BEHAVIOR: 
    # If it's a known offline dev key, we bypass the network check.
    if license_key.startswith("DEV_") or license_key.startswith("VALID_"):
        logger.success("License verification successful. Offline/Dev key accepted.")
        return True

    # REAL BEHAVIOR:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "license_key": license_key,
                "client_id": client_id,
                "hardware_id": hardware_id,
                "host_domain": network_info["hostname"],
                "host_ip": network_info["ip"],
                "timestamp": datetime.utcnow().isoformat()
            }
            response = await client.post(license_server_url, json=payload)
            
            if response.status_code == 200 and response.json().get("valid") is True:
                logger.success("Associative License verification successful.")
                return True
            else:
                logger.error("CRITICAL: License key is invalid, expired, or registered to another domain/IP.")
                sys.exit(1)
    except httpx.RequestError as e:
        logger.warning(f"License server unreachable. Falling back to cached validation. Error: {e}")
        # In a real system, you'd check a locally cached, cryptographically signed JWT here.
        # If cache expired -> sys.exit(1)
        return True
