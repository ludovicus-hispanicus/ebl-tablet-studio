import cv2
import numpy as np
import os
import shutil
from PIL import Image
import glob

HDR_SUFFIX = "_HDR"

def process_hdr_images(main_folder, subfolder_name):
    """
    Process HDR images by grouping them in sets of 3, creating HDR composites,
    and reorganizing them with sequential numbering.
    
    Args:
        main_folder: Path to the main folder containing subfolders
        subfolder_name: Name of the subfolder to process
    
    Returns:
        str: Path to the new subfolder containing processed images
    """
    print(f"    Starting HDR processing for {subfolder_name}")

    source_subfolder = os.path.join(main_folder, subfolder_name)
    
    if not os.path.exists(source_subfolder):
        print(f"      Error: Source subfolder {source_subfolder} does not exist")
        return None

    hdr_output_folder = os.path.join(main_folder, f"{subfolder_name}{HDR_SUFFIX}")
    os.makedirs(hdr_output_folder, exist_ok=True)

    image_pattern = os.path.join(source_subfolder, f"{subfolder_name}_*")
    all_images = glob.glob(image_pattern)
    
    print(f"      Looking for images in: {source_subfolder}")
    print(f"      Pattern: {image_pattern}")
    print(f"      Found: {[os.path.basename(img) for img in all_images]}")
    
    if not all_images:

        alternative_pattern = os.path.join(source_subfolder, "*")
        all_images = [img for img in glob.glob(alternative_pattern) 
                     if os.path.isfile(img) and img.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff'))]
        print(f"      Alternative search found: {[os.path.basename(img) for img in all_images]}")
    
    if not all_images:
        print(f"      Warning: No images found in {source_subfolder}")
        return None

    image_groups = {}
    for img_path in all_images:
        filename = os.path.basename(img_path)
        name_without_ext = os.path.splitext(filename)[0]

        try:
            parts = name_without_ext.split('_')
            if len(parts) >= 2:
                suffix = parts[-1]

                suffix_num = int(suffix)
                image_groups[suffix_num] = img_path
        except (ValueError, IndexError):
            print(f"      Warning: Could not parse suffix from {filename}")
            continue

    sorted_suffixes = sorted(image_groups.keys())
    print(f"      Sorted suffixes: {sorted_suffixes}")

    hdr_groups = []
    for i in range(0, len(sorted_suffixes), 3):
        group = []
        group_suffixes = []
        for j in range(3):
            if i + j < len(sorted_suffixes):
                suffix = sorted_suffixes[i + j]
                group.append(image_groups[suffix])
                group_suffixes.append(suffix)
        
        if len(group) == 3:
            hdr_groups.append((group, group_suffixes))
            print(f"      Created HDR group {len(hdr_groups)}: suffixes {group_suffixes}")
        elif len(group) > 0:
            print(f"      Warning: Incomplete group of {len(group)} images with suffixes {group_suffixes}, skipping")
    
    if not hdr_groups:
        print(f"      Warning: No complete groups of 3 images found for HDR processing")
        return None
    
    print(f"      Found {len(hdr_groups)} HDR groups to process")

    processed_images = []
    for group_idx, (image_group, group_suffixes) in enumerate(hdr_groups):
        try:
            print(f"      Processing HDR group {group_idx + 1}: {[os.path.basename(img) for img in image_group]}")

            hdr_result = create_hdr_image(image_group)
            
            if hdr_result is not None:

                output_filename = f"{subfolder_name}{HDR_SUFFIX}_{group_idx + 1:02d}.tif"
                output_path = os.path.join(hdr_output_folder, output_filename)

                cv2.imwrite(output_path, hdr_result)
                processed_images.append(output_path)
                
                print(f"      Created HDR image: {output_filename} from suffixes {group_suffixes}")
            else:
                print(f"      Failed to create HDR for group {group_idx + 1}")
                
        except Exception as e:
            print(f"      Error processing HDR group {group_idx + 1}: {e}")
    
    if processed_images:
        print(f"    HDR processing completed. {len(processed_images)} images created in {hdr_output_folder}")
        return hdr_output_folder
    else:
        print(f"    HDR processing failed - no images were created")
        return None


def create_hdr_image(image_paths):
    """
    Create an HDR image from a list of 3 exposure images using OpenCV.

    Args:
        image_paths: List of 3 image file paths with different exposures

    Returns:
        numpy.ndarray: HDR processed image as 16-bit array, or None if failed
    """
    try:

        img_list = []
        for path in image_paths:
            img = cv2.imread(path)
            if img is None:
                print(f"      Warning: Could not load image {path}")
                return None
            img_list.append(img)

        if len(img_list) != 3:
            print(f"      Warning: Expected 3 images, got {len(img_list)}")
            return None

        exposure_times = np.array([1.0, 2.0, 4.0], dtype=np.float32)

        try:
            merge_mertens = cv2.createMergeMertens(
                contrast_weight=1.0,
                saturation_weight=1.0,
                exposure_weight=0.0
            )
            res_mertens = merge_mertens.process(img_list)

            res_mertens_16bit = np.clip(
                res_mertens * 65535, 0, 65535).astype('uint16')
            return res_mertens_16bit

        except Exception as e:
            print(f"      Mertens fusion failed: {e}")

        try:

            merge_debevec = cv2.createMergeDebevec()
            hdr_debevec = merge_debevec.process(
                img_list, times=exposure_times.copy())

            tonemap = cv2.createTonemap(gamma=2.2)
            res_debevec = tonemap.process(hdr_debevec.copy())

            res_debevec_16bit = np.clip(
                res_debevec * 65535, 0, 65535).astype('uint16')
            return res_debevec_16bit

        except Exception as e:
            print(f"      Debevec HDR failed: {e}")

        print(f"      Using simple averaging as fallback")
        avg_img = np.mean(img_list, axis=0).astype('uint16')
        return avg_img

    except Exception as e:
        print(f"      HDR creation failed: {e}")
        return None


def align_images(img_list):
    """
    Align a list of images to compensate for camera movement.

    Args:
        img_list: List of OpenCV images

    Returns:
        List of aligned images
    """
    if len(img_list) < 2:
        return img_list

    try:

        ref_img = img_list[0]
        ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)

        aligned_images = [ref_img]

        for img in img_list[1:]:

            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            detector = cv2.ORB_create(5000)
            kp1, des1 = detector.detectAndCompute(ref_gray, None)
            kp2, des2 = detector.detectAndCompute(img_gray, None)

            if des1 is None or des2 is None:
                print(
                    f"        Warning: Could not detect features for alignment, using original image")
                aligned_images.append(img)
                continue

            matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = matcher.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)

            if len(matches) < 10:
                print(
                    f"        Warning: Not enough matches for alignment, using original image")
                aligned_images.append(img)
                continue

            src_pts = np.float32(
                [kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32(
                [kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

            M, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)

            if M is not None:

                h, w, c = ref_img.shape
                aligned_img = cv2.warpPerspective(img, M, (w, h))
                aligned_images.append(aligned_img)
            else:
                print(
                    f"        Warning: Could not compute homography, using original image")
                aligned_images.append(img)

        return aligned_images

    except Exception as e:
        print(f"        Image alignment failed: {e}, using original images")
        return img_list


def should_use_hdr_processing(main_folder, subfolder_name):
    """
    Check if HDR processing should be applied based on image naming patterns.
    
    Args:
        main_folder: Path to the main folder containing subfolders
        subfolder_name: Name of the subfolder to check
    
    Returns:
        bool: True if HDR processing should be applied
    """

    subfolder_path = os.path.join(main_folder, subfolder_name)
    
    if not os.path.exists(subfolder_path):
        print(f"    HDR check: Subfolder {subfolder_path} does not exist")
        return False

    image_pattern = os.path.join(subfolder_path, f"{subfolder_name}_*")
    all_images = glob.glob(image_pattern)

    if not all_images:
        all_images = [img for img in glob.glob(os.path.join(subfolder_path, "*"))
                     if os.path.isfile(img) and img.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff'))]
    
    print(f"    Checking HDR applicability for {subfolder_name}")
    print(f"    Found {len(all_images)} images in {subfolder_path}")
    print(f"    Images: {[os.path.basename(img) for img in all_images]}")
    
    numeric_suffixes = []
    for img_path in all_images:
        filename = os.path.basename(img_path)
        name_without_ext = os.path.splitext(filename)[0]
        
        try:

            parts = name_without_ext.split('_')
            if len(parts) >= 2:
                suffix = parts[-1]

                suffix_num = int(suffix)
                numeric_suffixes.append(suffix_num)
        except (ValueError, IndexError):
            print(f"      Skipping {filename}: non-numeric suffix")
            continue
    
    print(f"    Numeric suffixes found: {sorted(numeric_suffixes)}")

    is_applicable = len(numeric_suffixes) >= 3
    print(f"    HDR applicable: {is_applicable} (found {len(numeric_suffixes)} images with numeric suffixes)")
    
    return is_applicable


def test_hdr_processing():
    """Test function for HDR processing"""
    test_folder = r"C:\test_hdr"
    base_name = "TEST_TABLET"

    if os.path.exists(test_folder):
        result = process_hdr_images(test_folder, base_name)
        if result:
            print(f"HDR processing successful. Output folder: {result}")
        else:
            print("HDR processing failed")
    else:
        print(f"Test folder {test_folder} does not exist")


if __name__ == "__main__":
    test_hdr_processing()
