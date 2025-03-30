import os
import base64
import io
from PIL import Image
import numpy as np
import cv2
from flask import jsonify

# Check if Cerebras API key is available
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
USE_CEREBRAS = CEREBRAS_API_KEY is not None

# Initialize Cerebras client if API key is available
if USE_CEREBRAS:
    try:
        from cerebras.cloud.sdk import Cerebras
        cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
        print("Cerebras client initialized successfully")
    except ImportError:
        print("Cerebras SDK not installed")
        USE_CEREBRAS = False
    except Exception as e:
        print(f"Error initializing Cerebras client: {str(e)}")
        USE_CEREBRAS = False
else:
    print("No Cerebras API key found")

def enhance_image_with_cerebras(image_array):
    """
    Use Cerebras for advanced image enhancement
    
    Args:
        image_array: NumPy array of the image
    
    Returns:
        Enhanced image as NumPy array
    """
    # Always perform basic enhancement first
    enhanced = basic_image_enhancement(image_array)
    
    if not USE_CEREBRAS:
        return enhanced
    
    try:
        # Convert image to base64 for API transmission
        _, buffer = cv2.imencode('.png', enhanced)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Call Cerebras API for image enhancement
        prompt = """
        You are a specialized image enhancement AI. You're receiving a slide image 
        that needs to be optimized for OCR. Here are the steps to take:
        1. Correct perspective distortion if the slide appears skewed
        2. Enhance contrast to make text more readable
        3. Remove noise and artifacts that might interfere with text recognition
        4. Optimize the image specifically for OCR text extraction
        Return only the processed image data without any additional text or commentary.
        """
        
        # Using simpler API call without response_format parameter
        response = cerebras_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"<image>{img_base64}</image>"}
            ],
            model="llama3.1-8b",  # Using smaller model for faster processing
            max_tokens=1024
        )
        
        # Check if the response contains valid image data
        if hasattr(response.choices[0].message, 'content') and response.choices[0].message.content:
            try:
                # Try to extract and decode the enhanced image
                content = response.choices[0].message.content
                # Look for base64 image data
                if ';base64,' in content:
                    base64_img = content.split(';base64,')[1].split('"')[0]
                    enhanced_img_bytes = base64.b64decode(base64_img)
                    enhanced_img = np.array(Image.open(io.BytesIO(enhanced_img_bytes)))
                    return enhanced_img
            except Exception as e:
                print(f"Error processing Cerebras image response: {str(e)}")
        
        # If we get here, return the basic enhanced image
        return enhanced
        
    except Exception as e:
        print(f"Error in Cerebras image enhancement: {str(e)}")
        return enhanced

def extract_text_with_cerebras(image_array):
    """
    Use Cerebras for advanced OCR
    
    Args:
        image_array: NumPy array of the image
    
    Returns:
        Extracted text as string
    """
    if not USE_CEREBRAS:
        return "OCR processing unavailable - Cerebras API key required."
    
    try:
        # Convert image to base64 for API transmission
        _, buffer = cv2.imencode('.png', image_array)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Call Cerebras API for OCR
        prompt = """
        You are a specialized OCR AI. You're receiving a slide image that contains text.
        Your task is to extract all visible text from the image.
        Preserve the formatting and structure of the text as much as possible.
        Handle special characters, bullet points, and different font styles.
        Return only the extracted text, formatted as it appears in the slide.
        """
        
        # Using simpler API call
        response = cerebras_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"<image>{img_base64}</image>"}
            ],
            model="llama3.1-8b",  # Using smaller model for faster processing
            max_tokens=1024
        )
        
        if hasattr(response.choices[0].message, 'content') and response.choices[0].message.content:
            extracted_text = response.choices[0].message.content.strip()
            # Check if the response is valid text (not JSON or other format)
            if extracted_text and not extracted_text.startswith('{') and len(extracted_text) > 5:
                return extracted_text
            else:
                return "OCR processing resulted in invalid text format."
        else:
            return "OCR processing returned empty result."
            
    except Exception as e:
        print(f"Error in Cerebras OCR: {str(e)}")
        return f"OCR processing unavailable - Issue with OCR generated via Cerebras. Error: {str(e)}"

# Function to be used in your Flask routes
def process_slide_with_cerebras(image):
    """
    Process slide image with enhanced OCR capabilities
    
    Args:
        image: OpenCV image
    
    Returns:
        Dict with processed image and extracted text
    """
    try:
        # Create a copy of the original image
        original_image = image.copy()
        
        # Create an enhanced version for OCR
        enhanced_for_ocr = image.copy()
        
        # Convert to grayscale
        gray = cv2.cvtColor(enhanced_for_ocr, cv2.COLOR_BGR2GRAY)
        
        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)
        
        # Apply light thresholding to enhance text
        _, thresh = cv2.threshold(enhanced_gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Try to extract text directly using Cerebras if available
        extracted_text = ""
        try:
            if 'cerebras_client' in globals():
                # Convert image to base64
                _, buffer = cv2.imencode('.jpg', original_image)
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # Call Cerebras for text extraction
                response = cerebras_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Extract all visible text from this whiteboard image. Return only the text in plain format."},
                        {"role": "user", "content": f"<image>{img_base64}</image>"}
                    ],
                    model="llama3.1-8b",
                    max_tokens=1024
                )
                
                if hasattr(response.choices[0].message, 'content'):
                    extracted_text = response.choices[0].message.content
        except Exception as e:
            print(f"Cerebras OCR error: {e}")
            extracted_text = ""
        
        # If Cerebras failed, try a manual extraction approach
        if not extracted_text:
            extracted_text = """Facing issues while extracting OCR"""
            
        # Convert original image to base64 for client display
        _, buffer = cv2.imencode('.jpg', original_image)
        original_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            'success': True,
            'processed_image': f'data:image/jpeg;base64,{original_b64}',
            'text': extracted_text.strip()
        }
    except Exception as e:
        print(f"Error in image processing: {str(e)}")
        # Return original image on error
        _, buffer = cv2.imencode('.jpg', image)
        original_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            'success': True,
            'processed_image': f'data:image/jpeg;base64,{original_b64}',
            'text': "Error extracting text from image. Please try again with a clearer photo."
        }

# Basic image enhancement function that works without Cerebras
def basic_image_enhancement(image):
    """
    Basic image enhancement for better OCR
    
    Args:
        image: OpenCV image
    
    Returns:
        Enhanced image
    """
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding to improve contrast
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 21, 5
        )
        
        # Apply morphological operations to remove noise
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Convert back to BGR for consistency
        enhanced = cv2.cvtColor(opening, cv2.COLOR_GRAY2BGR)
        return enhanced
        
    except Exception as e:
        print(f"Error in basic image enhancement: {str(e)}")
        return image  # Return original on error