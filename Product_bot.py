import re
import requests
from bs4 import BeautifulSoup
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import urllib.parse
import time
from PIL import Image
import pytesseract
import io

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8414049375:AAFMPUvB2u5KffNPsaAi3xu_DOiy-7dhHIg"

# Supported platforms and shorteners
SUPPORTED_PLATFORMS = [
    'amazon', 'flipkart', 'meesho', 'myntra', 'ajio', 'snapdeal', 'wish'
]

SHORTENERS = [
    'cutt.ly', 'spoo.me', 'amzn-to.co', 'fkrt.cc', 'bitli.in', 'da.gd', 'wishlink.com'
]

# Default pin code for Meesho
DEFAULT_PIN_CODE = "110001"

def extract_urls(text):
    """Extract all URLs from text"""
    if not text:
        return []
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*(?:\?[\w=&]*)?'
    return re.findall(url_pattern, text)

def unshorten_url(url):
    """Follow redirects to get the final URL"""
    try:
        # Make request with proper headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # First, make a HEAD request to check if it's a shortener
        response = requests.head(url, allow_redirects=True, timeout=5, headers=headers)
        final_url = response.url
        
        # Check if it's still a shortener after following redirects
        for shortener in SHORTENERS:
            if shortener in final_url:
                # If still a shortener, make a GET request
                response = requests.get(url, allow_redirects=True, timeout=5, headers=headers)
                final_url = response.url
                break
                
        return final_url
    except Exception as e:
        logger.error(f"Error unshortening URL {url}: {str(e)}")
        return url  # Return original URL if unshortening fails

def clean_affiliate_url(url):
    """Remove affiliate parameters from URL"""
    try:
        # Parse the URL
        parsed_url = urllib.parse.urlparse(url)
        
        # Define affiliate parameters to remove for each platform
        affiliate_params = {
            'amazon': ['tag', 'ref', 'linkCode', 'camp', 'creative', 'linkId', 'psc', 'SubscriptionId'],
            'flipkart': ['affid', 'pid', 'sid', 'affsrc', 'icid', 'affExtParam1'],
            'meesho': ['aff_id', 'aff_source', 'aff_sub', 'aff_sub1', 'utm_source', 'utm_medium', 'utm_campaign'],
            'myntra': ['aff_id', 'source', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content'],
            'ajio': ['aff_id', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content'],
            'snapdeal': ['aff_id', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content'],
            'wish': ['aff_id', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content']
        }
        
        # Extract domain to determine platform
        domain = parsed_url.netloc.lower()
        platform = None
        
        if 'amazon' in domain:
            platform = 'amazon'
        elif 'flipkart' in domain:
            platform = 'flipkart'
        elif 'meesho' in domain:
            platform = 'meesho'
        elif 'myntra' in domain:
            platform = 'myntra'
        elif 'ajio' in domain:
            platform = 'ajio'
        elif 'snapdeal' in domain:
            platform = 'snapdeal'
        elif 'wish' in domain:
            platform = 'wish'
        
        # If we detected a platform, remove affiliate parameters
        if platform and platform in affiliate_params:
            query_params = urllib.parse.parse_qs(parsed_url.query)
            cleaned_params = {k: v for k, v in query_params.items() 
                             if k not in affiliate_params[platform]}
            
            # Rebuild the query string
            new_query = urllib.parse.urlencode(cleaned_params, doseq=True)
            cleaned_url = urllib.parse.urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment
            ))
            return cleaned_url
            
        return url  # Return original if no platform detected
    except Exception as e:
        logger.error(f"Error cleaning affiliate URL {url}: {str(e)}")
        return url  # Return original URL if cleaning fails

def detect_platform(url):
    """Detect e-commerce platform from URL"""
    domain = urllib.parse.urlparse(url).netloc.lower()
    
    if 'amazon' in domain:
        return 'amazon'
    elif 'flipkart' in domain:
        return 'flipkart'
    elif 'meesho' in domain:
        return 'meesho'
    elif 'myntra' in domain:
        return 'myntra'
    elif 'ajio' in domain:
        return 'ajio'
    elif 'snapdeal' in domain:
        return 'snapdeal'
    elif 'wish' in domain:
        return 'wish'
    
    return None

def extract_pin_code(text):
    """Extract pin code from message text"""
    if not text:
        return DEFAULT_PIN_CODE
    pin_pattern = r'\b\d{6}\b'
    matches = re.findall(pin_pattern, text)
    if matches:
        return matches[0]
    return DEFAULT_PIN_CODE

def clean_title(title, platform=None):
    """Clean product title based on platform rules"""
    if not title:
        return "Product"
    
    # Remove common marketing words and extra spaces
    marketing_words = [
        'best price', 'online shopping', 'buy now', 'free delivery', 
        'lowest price', 'discount', 'sale', 'offer', 'deal', 'limited time',
        '|', '-', '—', '–', '•', '★', '☆', '⭐', '₹', 'Rs.', 'Rs', 'INR', 'price',
        'only', 'just', 'hurry', 'limited', 'stock', 'available', 'now', 'online',
        'original', 'genuine', 'authentic', 'brand', 'new', 'latest', 'model',
        'combo', 'pack of', 'set of', 'bundle', 'combo pack'
    ]
    
    # Convert to lowercase for case-insensitive matching
    cleaned_title = title.lower()
    
    # Remove marketing words
    for word in marketing_words:
        cleaned_title = cleaned_title.replace(word.lower(), '')
    
    # Remove extra spaces and punctuation
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    cleaned_title = re.sub(r'[^\w\s]', '', cleaned_title).strip()
    
    # For Meesho, try to extract gender and quantity
    if platform == 'meesho':
        # Look for gender indicators
        gender = None
        if 'men' in cleaned_title or 'male' in cleaned_title:
            gender = 'Men'
            cleaned_title = re.sub(r'men|male', '', cleaned_title, flags=re.IGNORECASE)
        elif 'women' in cleaned_title or 'female' in cleaned_title or 'ladies' in cleaned_title or 'women' in cleaned_title:
            gender = 'Women'
            cleaned_title = re.sub(r'women|female|ladies', '', cleaned_title, flags=re.IGNORECASE)
        elif 'kids' in cleaned_title or 'child' in cleaned_title:
            gender = 'Kids'
            cleaned_title = re.sub(r'kids|child', '', cleaned_title, flags=re.IGNORECASE)
        
        # Look for quantity
        quantity = None
        quantity_match = re.search(r'(\d+)\s*(piece|pcs|pc|pack|set)', cleaned_title, re.IGNORECASE)
        if quantity_match:
            quantity = f"{quantity_match.group(1)}Pc"
            cleaned_title = re.sub(r'\d+\s*(piece|pcs|pc|pack|set)', '', cleaned_title, flags=re.IGNORECASE)
        
        # Clean up extra spaces again
        cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
        
        # Format title with gender and quantity if found
        if gender and quantity:
            return f"{gender} {quantity} {cleaned_title.title()}"
        elif gender:
            return f"{gender} {cleaned_title.title()}"
        elif quantity:
            return f"{quantity} {cleaned_title.title()}"
        else:
            return cleaned_title.title()
    
    # For clothing on other platforms
    elif platform in ['amazon', 'flipkart', 'myntra', 'ajio']:
        # Look for gender indicators
        gender = None
        if 'men' in cleaned_title or 'male' in cleaned_title:
            gender = 'Men'
            cleaned_title = re.sub(r'men|male', '', cleaned_title, flags=re.IGNORECASE)
        elif 'women' in cleaned_title or 'female' in cleaned_title or 'ladies' in cleaned_title:
            gender = 'Women'
            cleaned_title = re.sub(r'women|female|ladies', '', cleaned_title, flags=re.IGNORECASE)
        elif 'kids' in cleaned_title or 'child' in cleaned_title:
            gender = 'Kids'
            cleaned_title = re.sub(r'kids|child', '', cleaned_title, flags=re.IGNORECASE)
        
        # Clean up extra spaces again
        cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
        
        if gender:
            return f"{gender} {cleaned_title.title()}"
    
    # For non-clothing, just return cleaned title
    return cleaned_title.title()

def extract_price(text):
    """Extract price from text, returning only digits"""
    if not text:
        return None
    
    # Look for price patterns with ₹, Rs, or INR
    price_pattern = r'(?:₹|Rs|INR)\s*([\d,]+)'
    match = re.search(price_pattern, text)
    
    if match:
        # Remove commas and convert to integer
        price = match.group(1).replace(',', '')
        try:
            return int(price)
        except ValueError:
            return None
    
    # Look for standalone numbers that might be prices
    number_pattern = r'\b(\d{3,})\b'
    matches = re.findall(number_pattern, text)
    for num in matches:
        try:
            # Filter out numbers that are too large to be prices
            price = int(num.replace(',', ''))
            if 100 <= price <= 1000000:  # Reasonable price range
                return price
        except ValueError:
            continue
    
    return None

def get_meesho_sizes(soup):
    """Extract available sizes for Meesho products"""
    # Try to find size options in the page
    size_elements = soup.find_all(text=re.compile(r'size|size chart', re.IGNORECASE))
    
    available_sizes = []
    for element in size_elements:
        parent = element.find_parent()
        if parent:
            # Look for size options within the parent element
            size_options = parent.find_all(text=re.compile(r'\b(S|M|L|XL|XXL|Free Size)\b', re.IGNORECASE))
            for option in size_options:
                size = re.search(r'\b(S|M|L|XL|XXL|Free Size)\b', option, re.IGNORECASE)
                if size:
                    available_sizes.append(size.group(1).upper())
    
    # If we didn't find sizes through the above method, try more general approach
    if not available_sizes:
        all_elements = soup.find_all(text=re.compile(r'\b(S|M|L|XL|XXL|Free Size)\b', re.IGNORECASE))
        for element in all_elements:
            size = re.search(r'\b(S|M|L|XL|XXL|Free Size)\b', element, re.IGNORECASE)
            if size:
                available_sizes.append(size.group(1).upper())
    
    # Remove duplicates and sort
    available_sizes = list(set(available_sizes))
    
    # Check if all common sizes are available
    common_sizes = ['S', 'M', 'L', 'XL', 'XXL']
    if all(size in available_sizes for size in common_sizes):
        return "All"
    
    return ", ".join(available_sizes) if available_sizes else None

def scrape_amazon(url):
    """Scrape product details from Amazon"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title = None
        
        # Try og:title meta tag first
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content']
        else:
            # Try regular title tag
            if soup.title and soup.title.string:
                title = soup.title.string
        
        # If title is still not found, try h1 tags
        if not title:
            h1 = soup.find(id='productTitle') or soup.find(class_='a-size-large')
            if h1:
                title = h1.get_text(strip=True)
        
        # Extract price
        price = None
        price_element = soup.find(id='price') or soup.find(class_='a-price-whole')
        if price_element:
            price_text = price_element.get_text()
            price = extract_price(price_text)
        
        # If price not found, try other price elements
        if not price:
            price_elements = soup.find_all(class_='a-offscreen')
            for element in price_elements:
                price_text = element.get_text()
                price = extract_price(price_text)
                if price:
                    break
        
        return {
            'title': title,
            'price': price
        }
    
    except Exception as e:
        logger.error(f"Error scraping Amazon product from {url}: {str(e)}")
        return None

def scrape_flipkart(url):
    """Scrape product details from Flipkart"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title = None
        
        # Try og:title meta tag first
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content']
        else:
            # Try regular title tag
            if soup.title and soup.title.string:
                title = soup.title.string
        
        # If title is still not found, try h1 tags
        if not title:
            h1 = soup.find(class_='VU-ZEz') or soup.find(class_='yBlU7e')
            if h1:
                title = h1.get_text(strip=True)
        
        # Extract price
        price = None
        price_element = soup.find(class_='Nx9bqj') or soup.find(class_='_4xB0mG')
        if price_element:
            price_text = price_element.get_text()
            price = extract_price(price_text)
        
        return {
            'title': title,
            'price': price
        }
    
    except Exception as e:
        logger.error(f"Error scraping Flipkart product from {url}: {str(e)}")
        return None

def scrape_meesho(url, pin_code=DEFAULT_PIN_CODE):
    """Scrape product details from Meesho"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Cookie': f'pincode={pin_code}'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title = None
        
        # Try og:title meta tag first
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content']
        else:
            # Try regular title tag
            if soup.title and soup.title.string:
                title = soup.title.string
        
        # If title is still not found, try h1 tags
        if not title:
            h1 = soup.find(class_='-xw8y') or soup.find(class_='product-title')
            if h1:
                title = h1.get_text(strip=True)
        
        # Extract price
        price = None
        price_element = soup.find(class_='-xw8y') or soup.find(class_='_6k58m9')
        if price_element:
            price_text = price_element.get_text()
            price = extract_price(price_text)
        
        # Extract sizes
        sizes = get_meesho_sizes(soup)
        
        return {
            'title': title,
            'price': price,
            'sizes': sizes
        }
    
    except Exception as e:
        logger.error(f"Error scraping Meesho product from {url}: {str(e)}")
        return None

def scrape_product_details(url, platform, message_text="", pin_code=DEFAULT_PIN_CODE):
    """Scrape product details from URL based on platform"""
    if platform == 'amazon':
        return scrape_amazon(url)
    elif platform == 'flipkart':
        return scrape_flipkart(url)
    elif platform == 'meesho':
        return scrape_meesho(url, pin_code)
    # Add more platform-specific scrapers as needed
    
    # For other platforms, use a generic approach
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title = None
        
        # Try og:title meta tag first
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content']
        else:
            # Try regular title tag
            if soup.title and soup.title.string:
                title = soup.title.string
        
        # Extract price
        price = extract_price(response.text)
        
        return {
            'title': title,
            'price': price
        }
    
    except Exception as e:
        logger.error(f"Error scraping product details from {url}: {str(e)}")
        return None

def format_output(product_data, platform, url, message_text=""):
    """Format product details according to platform-specific rules"""
    # Extract pin code for Meesho
    pin_code = DEFAULT_PIN_CODE
    if platform == 'meesho':
        pin_code = extract_pin_code(message_text)
    
    # Format based on platform
    if platform == 'meesho':
        if not product_data or not product_data.get('title') or not product_data.get('price'):
            # Fallback for Meesho
            title = "Product"
            if product_data and product_data.get('title'):
                title = product_data['title']
            elif message_text:
                title = message_text.split('\n')[0][:50]
            
            price = product_data['price'] if product_data and product_data.get('price') else 0
            formatted_price = f"@{price} rs" if price else "@[Price] rs"
            
            output = f"{title} {formatted_price}\n{url}\n\n"
            output += f"Size - All\n"
            output += f"Pin - {pin_code}\n\n"
            output += "@reviewcheckk"
            return output
        
        # Clean the title
        cleaned_title = clean_title(product_data['title'], 'meesho')
        
        # Format price
        price = product_data['price']
        formatted_price = f"@{price} rs" if price else "@[Price] rs"
        
        # Format output
        output = f"{cleaned_title} {formatted_price}\n{url}\n\n"
        
        # Add sizes if available
        if product_data.get('sizes'):
            output += f"Size - {product_data['sizes']}\n"
        else:
            output += "Size - All\n"
        
        output += f"Pin - {pin_code}\n\n@reviewcheckk"
        
        return output
    
    elif platform in ['amazon', 'flipkart', 'myntra', 'ajio']:
        if not product_data or not product_data.get('title') or not product_data.get('price'):
            # Fallback for other platforms
            title = "Product"
            if product_data and product_data.get('title'):
                title = product_data['title']
            elif message_text:
                title = message_text.split('\n')[0][:50]
            
            price = product_data['price'] if product_data and product_data.get('price') else 0
            formatted_price = f"@{price} rs" if price else "@[Price] rs"
            
            # Check if it's clothing
            is_clothing = any(keyword in title.lower() for keyword in 
                             ['shirt', 't-shirt', 'jeans', 'jacket', 'dress', 'top', 'pants', 'trousers', 'saree', 'kurti', 'tshirt', 'kurta'])
            
            if is_clothing:
                cleaned_title = clean_title(title)
                return f"{cleaned_title} {formatted_price}\n{url}\n\n@reviewcheckk"
            else:
                # Try to extract brand (first word)
                title_parts = title.split()
                if len(title_parts) > 1:
                    brand = title_parts[0]
                    rest_title = ' '.join(title_parts[1:])
                    cleaned_title = f"{brand} {rest_title}"
                else:
                    cleaned_title = title
                
                return f"{cleaned_title} from {formatted_price}\n{url}\n\n@reviewcheckk"
        
        # Check if it's clothing
        is_clothing = any(keyword in product_data['title'].lower() for keyword in 
                         ['shirt', 't-shirt', 'jeans', 'jacket', 'dress', 'top', 'pants', 'trousers', 'saree', 'kurti', 'tshirt', 'kurta'])
        
        # Clean the title
        cleaned_title = clean_title(product_data['title'], platform)
        
        # Format price
        price = product_data['price']
        formatted_price = f"@{price} rs"
        
        if is_clothing:
            return f"{cleaned_title} {formatted_price}\n{url}\n\n@reviewcheckk"
        else:
            # Try to extract brand (first word)
            title_parts = cleaned_title.split()
            if len(title_parts) > 1:
                brand = title_parts[0]
                rest_title = ' '.join(title_parts[1:])
                cleaned_title = f"{brand} {rest_title}"
            
            return f"{cleaned_title} from {formatted_price}\n{url}\n\n@reviewcheckk"
    
    # For other platforms, use a generic format
    if product_data and product_data.get('title') and product_data.get('price'):
        title = clean_title(product_data['title'])
        price = product_data['price']
        formatted_price = f"@{price} rs"
        return f"{title} {formatted_price}\n{url}\n\n@reviewcheckk"
    
    # Final fallback - always return something
    title = "Product"
    if product_data and product_data.get('title'):
        title = product_data['title'][:50]
    elif message_text:
        title = message_text.split('\n')[0][:50]
    
    return f"{title} @[Price] rs\n{url}\n\n@reviewcheckk"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    message = update.effective_message
    if not message:
        return
    
    start_time = time.time()
    
    # Extract text from message
    message_text = message.text or ""
    
    # Check if there's a caption (for images)
    if not message_text and message.caption:
        message_text = message.caption
    
    # Extract URLs from the message
    urls = extract_urls(message_text)
    
    # Process each URL found
    for url in urls:
        try:
            # Unshorten the URL
            full_url = unshorten_url(url)
            
            # Clean affiliate parameters
            clean_url = clean_affiliate_url(full_url)
            
            # Detect platform
            platform = detect_platform(clean_url)
            if not platform or platform not in SUPPORTED_PLATFORMS:
                continue  # Skip if not a supported platform
            
            # Extract pin code from message (for Meesho)
            pin_code = extract_pin_code(message_text)
            
            # Scrape product details
            product_data = scrape_product_details(clean_url, platform, message_text, pin_code)
            
            # Format the output
            formatted_output = format_output(product_data, platform, clean_url, message_text)
            
            # Send the formatted message
            await message.reply_text(formatted_output)
                
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            # Always provide output even if there's an error
            try:
                clean_url = clean_affiliate_url(unshorten_url(url))
                platform = detect_platform(clean_url) or "Platform"
                
                output = f"Product @[Price] rs\n{clean_url}\n\n"
                if platform == 'meesho':
                    output += "Size - All\n"
                    output += f"Pin - {DEFAULT_PIN_CODE}\n\n"
                output += "@reviewcheckk"
                
                await message.reply_text(output)
            except:
                # Final fallback
                await message.reply_text(f"Product @[Price] rs\n{url}\n\n@reviewcheckk")
        
        # Ensure we don't exceed response time limit
        if time.time() - start_time > 2.5:
            break
    
    # Check if the message contains an image
    if (message.photo or (message.document and message.document.mime_type.startswith('image/'))):
        try:
            # Download the image
            if message.photo:
                # Get the largest photo
                photo_file = await context.bot.get_file(message.photo[-1].file_id)
            else:
                photo_file = await context.bot.get_file(message.document.file_id)
            
            image_bytes = await photo_file.download_as_bytearray()
            image = Image.open(io.BytesIO(image_bytes))
            
            # Use OCR to extract text
            ocr_text = pytesseract.image_to_string(image)
            
            # Extract URLs from OCR text
            ocr_urls = extract_urls(ocr_text)
            
            # Process each URL found in the image
            for url in ocr_urls:
                try:
                    full_url = unshorten_url(url)
                    clean_url = clean_affiliate_url(full_url)
                    platform = detect_platform(clean_url)
                    
                    if not platform or platform not in SUPPORTED_PLATFORMS:
                        continue
                    
                    pin_code = extract_pin_code(ocr_text)
                    product_data = scrape_product_details(clean_url, platform, ocr_text, pin_code)
                    
                    formatted_output = format_output(product_data, platform, clean_url, ocr_text)
                    
                    # Forward the original image with the formatted message
                    await message.reply_photo(
                        photo=message.photo[-1].file_id if message.photo else message.document.file_id,
                        caption=formatted_output
                    )
                
                except Exception as e:
                    logger.error(f"Error processing image URL {url}: {str(e)}")
                    # Always provide output even if there's an error
                    try:
                        clean_url = clean_affiliate_url(unshorten_url(url))
                        output = f"Product @[Price] rs\n{clean_url}\n\n@reviewcheckk"
                        await message.reply_photo(
                            photo=message.photo[-1].file_id if message.photo else message.document.file_id,
                            caption=output
                        )
                    except:
                        pass
            
            # If no URLs were found in the image, but there's text that could be a product title
            if not ocr_urls and ocr_text.strip():
                # Create a minimal product post from the OCR text
                try:
                    # Extract price if available
                    price = extract_price(ocr_text)
                    price_text = f"@{price} rs" if price else "@[Price] rs"
                    
                    # Clean the OCR text as title
                    title = clean_title(ocr_text)
                    
                    # Create a message
                    output = f"{title} {price_text}\n\n@reviewcheckk"
                    await message.reply_text(output)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            # Skip image processing if there's an error

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handler to process all messages
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Document.IMAGE, 
        handle_message
    ))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
