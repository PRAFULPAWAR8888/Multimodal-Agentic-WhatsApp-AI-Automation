from whatsapp_agent.config.settings import VisionProvider, get_settings
from whatsapp_agent.core.exceptions import VisionError

_vision_provider_instance = None

def get_vision_provider():
    """Factory to return the configured Vision Provider singleton."""
    global _vision_provider_instance
    if _vision_provider_instance is not None:
        return _vision_provider_instance

    settings = get_settings()
    provider_type = settings.vision_provider

    if provider_type == VisionProvider.MOONDREAM:
        from whatsapp_agent.vision.moondream import MoondreamProvider
        _vision_provider_instance = MoondreamProvider()
    elif provider_type == VisionProvider.QWEN:
        from whatsapp_agent.vision.qwen import QwenProvider
        _vision_provider_instance = QwenProvider()
    else:
        raise VisionError(f"Unsupported vision provider: {provider_type}")

    return _vision_provider_instance
