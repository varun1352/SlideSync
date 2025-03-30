import os
import base64
import io
from PIL import Image
import numpy as np
import cv2
import secrets
import time

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

def preprocess_image_for_ocr(image):
    """
    Preprocess image to make it suitable for OCR and reduce size
    
    Args:
        image: NumPy array of the image
        
    Returns:
        Preprocessed image as NumPy array
    """
    # Resize large images
    max_dimension = 1600  # Maximum dimension (width or height)
    height, width = image.shape[:2]
    
    # Check if resizing is needed
    if height > max_dimension or width > max_dimension:
        # Calculate new dimensions while preserving aspect ratio
        if height > width:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))
        else:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        
        # Resize the image
        image = cv2.resize(image, (new_width, new_height))
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply thresholding to improve OCR
    _, threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return threshold

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
        # Preprocess image to reduce size
        preprocessed = preprocess_image_for_ocr(image_array)
        
        # Convert image to base64 for API transmission
        _, buffer = cv2.imencode('.jpg', preprocessed, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Call Cerebras API for image enhancement with simpler prompt
        prompt = "Enhance this image for OCR readability. Adjust contrast, remove noise, and optimize for text detection."
        
        # Using simpler API call without response_format parameter
        response = cerebras_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"<image>{img_base64}</image>"}
            ],
            model="llama3.1-8b",  # Using smaller model for faster processing
            max_tokens=256
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

def extract_text_from_image_chunk(chunk, chunk_index=0):
    """
    Extract text from a single image chunk using Cerebras
    
    Args:
        chunk: Image chunk as NumPy array
        chunk_index: Index of the chunk for logging
        
    Returns:
        Extracted text as string
    """
    if not USE_CEREBRAS:
        return "OCR processing unavailable - Cerebras API key required."
    
    try:
        # Convert chunk to base64
        _, buffer = cv2.imencode('.jpg', chunk, [cv2.IMWRITE_JPEG_QUALITY, 85])
        chunk_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Very simple prompt to reduce token usage
        prompt = "Extract text from this image, output text only."
        
        # Call Cerebras with minimal parameters
        response = cerebras_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"<image>{chunk_base64}</image>"}
            ],
            model="llama3.1-8b",
            max_tokens=512,
            temperature=0.0
        )
        
        if hasattr(response.choices[0].message, 'content') and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        else:
            return ""
    except Exception as e:
        print(f"Error extracting text from chunk {chunk_index}: {str(e)}")
        # Add a delay before retrying to avoid rate limits
        time.sleep(2)
        return ""

def extract_text_with_cerebras(image_array):
    """
    Use Cerebras for advanced OCR with image chunking
    
    Args:
        image_array: NumPy array of the image
    
    Returns:
        Extracted text as string
    """
    if not USE_CEREBRAS:
        return "OCR processing unavailable - Cerebras API key required."
    
    try:
        # Preprocess image
        processed_image = preprocess_image_for_ocr(image_array)
        
        # For large images, divide into chunks
        height, width = processed_image.shape[:2]
        
        # Determine if we need to chunk the image
        if height * width > 1000000:  # Roughly 1 megapixel
            # Split image into quadrants
            chunks = []
            
            # Calculate quadrant dimensions
            h_mid = height // 2
            w_mid = width // 2
            
            # Create 4 quadrants
            chunks.append(processed_image[0:h_mid, 0:w_mid])  # Top-left
            chunks.append(processed_image[0:h_mid, w_mid:])   # Top-right
            chunks.append(processed_image[h_mid:, 0:w_mid])   # Bottom-left
            chunks.append(processed_image[h_mid:, w_mid:])    # Bottom-right
            
            # Process each chunk
            extracted_texts = []
            for i, chunk in enumerate(chunks):
                # Convert chunk to grayscale if it's not already
                if len(chunk.shape) == 3:
                    chunk = cv2.cvtColor(chunk, cv2.COLOR_BGR2GRAY)
                    
                # Extract text from this chunk
                chunk_text = extract_text_from_image_chunk(chunk, i)
                if chunk_text:
                    extracted_texts.append(chunk_text)
                    
                # Add delay between API calls to avoid rate limits
                if i < len(chunks) - 1:
                    time.sleep(1)
            
            # Combine extracted text from all chunks
            return "\n\n".join(extracted_texts)
        else:
            # Small enough to process as one image
            return extract_text_from_image_chunk(processed_image)
            
    except Exception as e:
        print(f"Error in Cerebras OCR: {str(e)}")
        return f"OCR processing unavailable - Issue with OCR service. Error: {str(e)}"

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
        
        # Resize large images to prevent token limit issues
        height, width = original_image.shape[:2]
        if height > 2000 or width > 2000:
            # Calculate new dimensions while preserving aspect ratio
            if height > width:
                new_height = 2000
                new_width = int(width * (2000 / height))
            else:
                new_width = 2000
                new_height = int(height * (2000 / width))
            
            # Resize the image
            resized_image = cv2.resize(original_image, (new_width, new_height))
        else:
            resized_image = original_image
        
        # Try to extract text using Cerebras with chunking approach
        extracted_text = ""
        try:
            if USE_CEREBRAS:
                extracted_text = extract_text_with_cerebras(resized_image)
        except Exception as e:
            print(f"Cerebras OCR error: {e}")
            extracted_text = "Error extracting text. Please try again with a clearer photo."
        
        # If Cerebras failed or returned empty text, provide a fallback message
        if not extracted_text or extracted_text.strip() == "":
            extracted_text = "Unable to extract text from this image. Try a clearer photo or different angle."
            
        # Convert original image to base64 for client display
        _, buffer = cv2.imencode('.jpg', original_image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        original_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            'success': True,
            'processed_image': f'data:image/jpeg;base64,{original_b64}',
            'text': extracted_text.strip()
        }
    except Exception as e:
        print(f"Error in image processing: {str(e)}")
        # Return original image on error
        try:
            _, buffer = cv2.imencode('.jpg', image)
            original_b64 = base64.b64encode(buffer).decode('utf-8')
            
            return {
                'success': True,
                'processed_image': f'data:image/jpeg;base64,{original_b64}',
                'text': "Error extracting text from image. Please try again with a clearer photo."
            }
        except:
            # Last resort fallback
            return {
                'success': False,
                'error': f"Failed to process image: {str(e)}"
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
        # Create a copy to avoid modifying the original
        img = image.copy()
        
        # Convert to grayscale if it's not already
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        
        # Apply adaptive thresholding to improve contrast
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 21, 5
        )
        
        # Apply morphological operations to remove noise
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Convert back to BGR for consistency
        if len(img.shape) == 3:
            enhanced = cv2.cvtColor(opening, cv2.COLOR_GRAY2BGR)
        else:
            enhanced = opening
        
        return enhanced
        
    except Exception as e:
        print(f"Error in basic image enhancement: {str(e)}")
        return image  # Return original on error