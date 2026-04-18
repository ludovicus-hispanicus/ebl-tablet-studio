import cv2
import numpy as np
import os
from PIL import Image

def rotate_image(image_path, angle, output_path=None):
    """
    Rotate an image by the specified angle.
    
    Args:
        image_path (str): Path to input image
        angle (int): Rotation angle (90, 180, 270)
        output_path (str): Path for output image (if None, overwrites input)
    
    Returns:
        str: Path to the rotated image
    """
    if angle == 0:
        return image_path
    
    try:

        with Image.open(image_path) as img:
            if angle == 90:
                rotated = img.transpose(Image.ROTATE_270)  # PIL's 270 = our 90 clockwise
            elif angle == 180:
                rotated = img.transpose(Image.ROTATE_180)
            elif angle == 270:
                rotated = img.transpose(Image.ROTATE_90)   # PIL's 90 = our 270 clockwise
            else:
                print(f"Warning: Unsupported rotation angle {angle}. Skipping rotation.")
                return image_path

            save_path = output_path if output_path else image_path
            rotated.save(save_path, quality=95 if save_path.lower().endswith('.jpg') else None)
            
            print(f"    Rotated {os.path.basename(image_path)} by {angle}°")
            return save_path
            
    except Exception as e:
        print(f"Error rotating {image_path}: {e}")
        return image_path

def rotate_images_in_folder(folder_path, angle, image_extensions):
    """
    Rotate all images in a folder by the specified angle.
    
    Args:
        folder_path (str): Path to folder containing images
        angle (int): Rotation angle (90, 180, 270)
        image_extensions (tuple): Tuple of valid image extensions
    
    Returns:
        int: Number of images rotated
    """
    if angle == 0:
        return 0
        
    rotated_count = 0
    
    try:
        for filename in os.listdir(folder_path):
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                image_path = os.path.join(folder_path, filename)
                if os.path.isfile(image_path):
                    rotate_image(image_path, angle)
                    rotated_count += 1
                    
    except Exception as e:
        print(f"Error rotating images in {folder_path}: {e}")
    
    return rotated_count