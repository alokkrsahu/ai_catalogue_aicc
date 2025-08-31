#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modern Gemini API PDF Text Extractor
Uses Google Gemini 2.5 Flash API for PDF and scanned image text extraction
Upgraded to use the latest google.genai library and gemini-2.5-flash model
"""

import logging
import base64
import tempfile
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class ModernGeminiPDFExtractor:
    """Modern PDF and scanned image text extractor using Gemini 2.5 Flash API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.gemini_available = False
        self.client = None
        self.use_fallback = False
        
        if self.api_key:
            try:
                # Import new Gemini library
                from google import genai
                from google.genai import types
                
                # Configure the client with API key
                os.environ['GOOGLE_API_KEY'] = self.api_key
                self.client = genai.Client()
                self.genai = genai
                self.types = types
                
                # Test the connection
                self._test_connection()
                self.gemini_available = True
                logger.info("✅ Modern Gemini 2.5 Flash API configured successfully")
                
            except ImportError as e:
                logger.error("❌ google-genai not installed. Run: pip install google-genai")
                logger.error(f"Import error details: {e}")
                # Fallback to old library if available
                self._try_fallback_library()
            except Exception as e:
                logger.error(f"❌ Failed to configure Modern Gemini API: {e}")
                # Fallback to old library if available
                self._try_fallback_library()
        else:
            logger.warning("⚠️ No Gemini API key provided")
    
    def _test_connection(self):
        """Test the Gemini connection with a simple request"""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Hello, test connection."
            )
            logger.info("✅ Gemini 2.5 Flash connection test successful")
        except Exception as e:
            logger.warning(f"⚠️ Gemini connection test failed: {e}")
    
    def _try_fallback_library(self):
        """Fallback to old google-generativeai library if new one fails"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.old_model = genai.GenerativeModel('gemini-1.5-flash')
            self.gemini_available = True
            self.use_fallback = True
            logger.warning("⚠️ Using fallback to old Gemini 1.5 Flash API")
        except Exception as e:
            logger.error(f"❌ Both new and old Gemini libraries failed: {e}")
            self.use_fallback = False
    
    def extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF using Modern Gemini 2.5 Flash API"""
        if not self.gemini_available:
            logger.warning("Gemini API not available, falling back to PyPDF2")
            return self._fallback_pdf_extraction(file_path)
        
        try:
            logger.info(f"🔍 Extracting PDF text using Modern Gemini 2.5 Flash API: {file_path}")
            
            # Convert PDF to images for Gemini processing
            images = self._pdf_to_images(file_path)
            
            if not images:
                logger.warning("No images extracted from PDF, falling back to PyPDF2")
                return self._fallback_pdf_extraction(file_path)
            
            extracted_text = []
            
            for i, image_data in enumerate(images):
                try:
                    page_text = self._extract_text_from_image(image_data, f"page {i+1}")
                    if page_text:
                        extracted_text.append(page_text)
                        logger.info(f"  ✅ Extracted text from page {i+1}: {len(page_text)} chars")
                    
                except Exception as e:
                    logger.error(f"  ❌ Error processing page {i+1}: {e}")
                    continue
            
            if extracted_text:
                combined_text = "\n\n".join(extracted_text)
                logger.info(f"✅ Modern Gemini PDF extraction successful: {len(combined_text)} total chars")
                return combined_text
            else:
                logger.warning("No text extracted via Modern Gemini, falling back to PyPDF2")
                return self._fallback_pdf_extraction(file_path)
                
        except Exception as e:
            logger.error(f"❌ Modern Gemini PDF extraction failed: {e}")
            return self._fallback_pdf_extraction(file_path)
    
    def _extract_text_from_image(self, image_data: str, page_info: str = "") -> str:
        """Extract text from a single image using Gemini 2.5 Flash"""
        try:
            # Enhanced prompt for better text extraction
            prompt = (
                "You are an expert document analysis AI. Please extract ALL text from this document image with high accuracy. "
                "Instructions:\n"
                "1. Extract every word, number, and symbol visible in the image\n"
                "2. Maintain the original structure, formatting, and layout as much as possible\n"
                "3. Preserve paragraph breaks, bullet points, and section divisions\n"
                "4. If you see tables, maintain the table structure\n"
                "5. Include headers, footers, and any marginal text\n"
                "6. If text is partially obscured or unclear, make your best interpretation\n"
                "7. Do not add any commentary or explanations - return ONLY the extracted text\n\n"
                "Please extract the text now:"
            )
            
            if self.use_fallback:
                # Use old API as fallback
                response = self.old_model.generate_content([
                    prompt,
                    {
                        "mime_type": "image/png",
                        "data": image_data
                    }
                ])
                return response.text.strip() if response.text else ""
            
            else:
                # Use new Gemini 2.5 Flash API
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/png",
                                        "data": image_data
                                    }
                                }
                            ]
                        }
                    ]
                )
                
                # Extract text from response
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts') and candidate.content.parts:
                            text_parts = []
                            for part in candidate.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    text_parts.append(part.text)
                            return "\n".join(text_parts).strip()
                
                return ""
                
        except Exception as e:
            logger.error(f"❌ Error extracting text from {page_info}: {e}")
            return ""
    
    def _pdf_to_images(self, pdf_path: str) -> list:
        """Convert PDF pages to images for Gemini processing"""
        try:
            # Try using pdf2image first
            try:
                from pdf2image import convert_from_path
                import io
                
                logger.info("Converting PDF to images using pdf2image...")
                
                # Convert PDF to PIL images
                images = convert_from_path(
                    pdf_path, 
                    dpi=200  # Good quality for OCR
                )
                
                image_data_list = []
                for image in images:
                    # Convert PIL image to base64
                    img_buffer = io.BytesIO()
                    image.save(img_buffer, format='PNG')
                    img_data = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                    image_data_list.append(img_data)
                
                logger.info(f"  ✅ Converted {len(image_data_list)} pages to images")
                return image_data_list
                
            except ImportError:
                logger.warning("pdf2image not available, trying alternative approach")
                
            # Fallback: try using fitz (PyMuPDF)
            try:
                import fitz  # PyMuPDF
                import io
                
                logger.info("Converting PDF to images using PyMuPDF...")
                
                doc = fitz.open(pdf_path)
                image_data_list = []
                
                # Process all pages
                max_pages = len(doc)
                
                for page_num in range(max_pages):
                    page = doc[page_num]
                    # Render page as image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                    img_data = pix.tobytes("png")
                    img_b64 = base64.b64encode(img_data).decode('utf-8')
                    image_data_list.append(img_b64)
                
                doc.close()
                logger.info(f"  ✅ Converted {len(image_data_list)} pages to images")
                return image_data_list
                
            except ImportError:
                logger.warning("PyMuPDF not available")
                
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
        
        return []
    
    def _fallback_pdf_extraction(self, file_path: str) -> str:
        """Fallback PDF extraction using PyPDF2"""
        try:
            import PyPDF2
            logger.info(f"Using PyPDF2 fallback for: {file_path}")
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_content = []
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(page_text)
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}: {e}")
                
                content = '\n\n'.join(text_content)
                if content and len(content.strip()) > 10:
                    logger.info(f"✅ PyPDF2 fallback successful: {len(content)} chars")
                    return content
                    
        except Exception as e:
            logger.error(f"PyPDF2 fallback failed: {e}")
        
        return ""
    
    def extract_image_text(self, image_path: str) -> str:
        """Extract text from scanned images using Modern Gemini API"""
        if not self.gemini_available:
            logger.warning("Gemini API not available for image text extraction")
            return ""
        
        try:
            logger.info(f"🔍 Extracting text from image using Modern Gemini 2.5 Flash API: {image_path}")
            
            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Extract text using the modern API
            extracted_text = self._extract_text_from_image(image_data, "image")
            
            if extracted_text:
                logger.info(f"✅ Modern Gemini image extraction successful: {len(extracted_text)} chars")
                return extracted_text
            else:
                logger.warning("No text extracted from image")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Modern Gemini image extraction failed: {e}")
            return ""

# Backward compatibility - keep the old class name as alias
GeminiPDFExtractor = ModernGeminiPDFExtractor

# Global instance (will be initialized with API key)
gemini_extractor = None

def initialize_gemini_extractor(api_key: str):
    """Initialize the global Modern Gemini extractor with API key"""
    global gemini_extractor
    gemini_extractor = ModernGeminiPDFExtractor(api_key)
    logger.info("🚀 Initialized Modern Gemini 2.5 Flash PDF Extractor")
    return gemini_extractor

def get_gemini_extractor() -> Optional[ModernGeminiPDFExtractor]:
    """Get the global Modern Gemini extractor instance"""
    return gemini_extractor
