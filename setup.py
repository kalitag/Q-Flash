from setuptools import setup, find_packages

setup(
    name="product-telegram-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot==20.6",
        "requests==2.31.0",
        "beautifulsoup4==4.12.2",
        "Pillow==10.2.0",
        "pytesseract==0.3.10",
        "lxml==5.2.1",
        "regex==2023.12.25"
    ],
    entry_points={
        "console_scripts": [
            "product-bot=Product_bot:main",
        ],
    },
    author="Your Name",
    description="Telegram bot for processing e-commerce product links",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/kalitag/Q-Flash",
)
