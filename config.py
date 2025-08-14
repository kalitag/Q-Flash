# Configuration file for Product Telegram Bot

# Bot token - should be set as environment variable in production
# For development, you can uncomment the line below (not recommended for production)
# BOT_TOKEN = "8414049375:AAFMPUvB2u5KffNPsaAi3xu_DOiy-7dhHIg"

# Default pin code for Meesho
DEFAULT_PIN_CODE = "110001"

# Supported e-commerce platforms
SUPPORTED_PLATFORMS = [
    'amazon', 'flipkart', 'meesho', 'myntra', 'ajio', 'snapdeal', 'wish'
]

# URL shorteners to detect and unshorten
SHORTENERS = [
    'cutt.ly', 'spoo.me', 'amzn-to.co', 'fkrt.cc', 'bitli.in', 'da.gd', 'wishlink.com'
]

# Maximum response time in seconds
MAX_RESPONSE_TIME = 2.5
