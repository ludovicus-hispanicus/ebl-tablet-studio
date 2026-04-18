import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

script_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lib_directory = os.path.join(script_directory, "lib")
tests_directory = os.path.dirname(os.path.abspath(__file__))

for directory in [lib_directory, tests_directory]:
    if directory not in sys.path:
        sys.path.insert(0, directory)

from test_config import EXPECTED_MEASUREMENTS

sys.path.insert(0, lib_directory)
from ruler_detector_iraq_museum import detect_1cm_distance_iraq, get_detection_parameters


def test_with_timeout(image_path, museum_selection, timeout_seconds=30):
    def run_detection():
        try:
            return detect_1cm_distance_iraq(image_path, museum_selection=museum_selection)
        except Exception as e:
            return {'error': str(e)}

    start_time = time.time()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_detection)
            result = future.result(timeout=timeout_seconds)
            elapsed_time = time.time() - start_time

            if isinstance(result, dict) and 'error' in result:
                return None, elapsed_time, result['error']
            return result, elapsed_time, None
    except FutureTimeoutError:
        elapsed_time = time.time() - start_time
        return None, elapsed_time, f"Function call timed out after {timeout_seconds} seconds"
    except Exception as e:
        elapsed_time = time.time() - start_time
        return None, elapsed_time, str(e)


def quick_diagnostic():
    test_images_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Examples", "Sippar")
    if not os.path.exists(test_images_path):
        print(f"ERROR: Test images directory not found: {test_images_path}")
        return

    print("Quick Diagnostic Test (with 30-second timeout per image)")
    print("=" * 60)
    
    total_images = len(EXPECTED_MEASUREMENTS)
    successful_detections = 0
    timeouts = 0
    errors = 0
    
    for i, (image_name, expected_data) in enumerate(EXPECTED_MEASUREMENTS.items(), 1):
        image_path = os.path.join(test_images_path, image_name)
        if not os.path.exists(image_path):
            print(f"WARNING [{i}/{total_images}] SKIP: {image_name} - File not found")
            continue

        print(f"\n[{i}/{total_images}] Testing: {image_name}")
        print(f"Expected: {expected_data['expected']} px (range: {expected_data['min']}-{expected_data['max']})")
        
        result, elapsed_time, error = test_with_timeout(
            image_path, 
            "Iraq Museum (Sippar Library)", 
            timeout_seconds=30
        )
        
        if error and "timed out" in error:
            print(f"TIMEOUT: Took longer than 30 seconds")
            timeouts += 1
        elif error:
            print(f"ERROR: {error}")
            errors += 1
        elif result is None:
            print(f"FAIL: No detection (took {elapsed_time:.1f}s)")
        elif expected_data['min'] <= result <= expected_data['max']:
            difference = abs(result - expected_data['expected'])
            print(f"PASS: {result} px (error: {difference:.1f} px, took {elapsed_time:.1f}s)")
            successful_detections += 1
        else:
            print(f"FAIL: {result} px - outside range (took {elapsed_time:.1f}s)")

    print(f"\n" + "=" * 60)
    print("QUICK DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"Total images: {total_images}")
    print(f"Successful detections: {successful_detections}")
    print(f"Timeouts (>30s): {timeouts}")
    print(f"Errors: {errors}")
    print(f"Success rate: {successful_detections/total_images*100:.1f}%")
    
    if timeouts > 0:
        print(f"\nWARNING: {timeouts} images timed out - detection function may be hanging")
    if successful_detections == 0:
        print("\nCRITICAL: No images detected successfully")
        print("Recommendation: Run parameter optimization first")
    elif successful_detections < total_images // 2:
        print(f"\nLOW SUCCESS RATE: Only {successful_detections}/{total_images} images working")
        print("Recommendation: Optimize parameters for better performance")
    else:
        print(f"\nGOOD: {successful_detections}/{total_images} images working")
    
    params = get_detection_parameters("Iraq Museum (Sippar Library)")
    print(f"Parameters: {params}")


if __name__ == "__main__":
    print("Ruler Detection Quick Diagnostic (Windows Compatible)")
    print("=" * 60)
    quick_diagnostic()
    print("\n" + "=" * 60)
    print("Diagnostic complete.")
    print("If there were timeouts or no detections, run parameter optimization:")
    print("python ruler_detector_iraq_museum_sippar_library_finetuning.test.py --flexible")