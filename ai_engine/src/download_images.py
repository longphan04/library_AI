"""
Image Download Module

Downloads book cover images from Google Books URLs
and saves them as book/{identifier}.jpg format.
"""

import os
import sys
import json
import glob
import requests
from PIL import Image
from io import BytesIO

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

class ImageDownloader:
    def __init__(self, output_dir=None):
        if output_dir is None:
            output_dir = os.path.join(settings.BASE_DIR, "data", "export", "book")
        self.output_dir = output_dir
        self.stats = {
            "total": 0,
            "downloaded": 0,
            "skipped": 0,
            "errors": 0
        }
    
    def download_image(self, url, identifier):
        """
        Download single image from URL and save as JPEG
        
        Returns: "success", "skipped", or "error"
        """
        output_path = os.path.join(self.output_dir, f"{identifier}.jpg")
        
        # Skip if exists
        if os.path.exists(output_path):
            return "skipped"
        
        try:
            # Download with timeout
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Open image
            img = Image.open(BytesIO(response.content))
            
            # Convert RGBA/PNG to RGB for JPEG
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                # Paste with alpha channel as mask
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if len(img.split()) > 3 else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as JPEG with good quality
            img.save(output_path, 'JPEG', quality=85, optimize=True)
            return "success"
            
        except requests.RequestException as e:
            print(f"  ✗ Network error for {identifier}: {str(e)[:50]}")
            return "error"
        except Exception as e:
            print(f"  ✗ Error processing {identifier}: {str(e)[:50]}")
            return "error"
    
    def download_all(self, books):
        """Download images for all books with progress tracking"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"Output directory: {self.output_dir}")
        print(f"Starting download for {len(books)} books...\n")
        
        for i, book in enumerate(books, 1):
            identifier = book.get('identifier')
            cover_url = book.get('cover_url')
            
            if not cover_url or not identifier:
                continue
            
            self.stats["total"] += 1
            
            # Try main cover_url first
            result = self.download_image(cover_url, identifier)
            
            if result == "success":
                self.stats["downloaded"] += 1
                if i % 10 == 0:
                    print(f"  ✓ Downloaded {self.stats['downloaded']} images...")
            elif result == "skipped":
                self.stats["skipped"] += 1
            else:
                # Try small_thumbnail as fallback
                small_url = book.get('small_thumbnail')
                if small_url:
                    result = self.download_image(small_url, identifier)
                    if result == "success":
                        self.stats["downloaded"] += 1
                    else:
                        self.stats["errors"] += 1
                else:
                    self.stats["errors"] += 1
        
        # Final summary
        print("\n" + "="*60)
        print("DOWNLOAD COMPLETE")
        print("="*60)
        print(f"Total books:          {self.stats['total']}")
        print(f"Successfully downloaded: {self.stats['downloaded']}")
        print(f"Already existed:      {self.stats['skipped']}")
        print(f"Errors/Failed:        {self.stats['errors']}")
        print(f"\nOutput: {self.output_dir}")
        print("="*60)

def download_images():
    """Main function to download all book cover images"""
    print("="*60)
    print("IMAGE DOWNLOAD MODULE")
    print("="*60)
    
    # Load processed books
    pattern = os.path.join(settings.DATA_PROCESSED_DIR, "clean_books_*.json")
    files = glob.glob(pattern)
    
    if not files:
        print("No processed files found!")
        return
    
    all_books = []
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            all_books.extend(json.load(f))
    
    print(f"Loaded {len(all_books)} processed books\n")
    
    # Download
    downloader = ImageDownloader()
    downloader.download_all(all_books)

if __name__ == "__main__":
    download_images()
