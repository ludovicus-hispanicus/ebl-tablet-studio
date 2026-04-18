'''
Search complete: 86.8min, 1901 iterations
Best coverage: 7/7 (100.0%)
Search rate: 0.4 iterations/second

Parameters: {'num_ticks_for_1cm': 11, 'hough_threshold': 19, 'hough_min_line_length': 13, 'hough_max_line_gap': 50, 'tick_max_width': 11, 'tick_min_width': 2, 'tick_min_height': 51, 'max_tick_thickness_px': 39, 'min_ticks_required': 6, 'consistency_threshold': 0.87, 'canny_low_threshold': 22, 'canny_high_threshold': 122, 'roi_height_fraction': 0.48, 'text_match_threshold': 0.42}
'''

import os
import sys
import time
import argparse
import random
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed

script_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lib_directory = os.path.join(script_directory, "lib")
tests_directory = os.path.dirname(os.path.abspath(__file__))

for directory in [lib_directory, tests_directory]:
    if directory not in sys.path:
        sys.path.insert(0, directory)

from test_config import EXPECTED_MEASUREMENTS

sys.path.insert(0, lib_directory)
from ruler_detector_iraq_museum import detect_1cm_distance_iraq, get_detection_parameters


def test_single_parameter_set(args):
    params, test_images_path, expected_measurements, museum_selection = args
    
    results = {}
    successful = 0
    total_error = 0
    
    for image_name, expected_data in expected_measurements.items():
        image_path = os.path.join(test_images_path, image_name)
        if not os.path.exists(image_path):
            continue
        
        try:
            detected = detect_1cm_distance_iraq(image_path, 
                                              museum_selection=museum_selection, 
                                              params=params)
        except Exception:
            detected = None

        results[image_name] = detected
        
        if detected and expected_data['min'] <= detected <= expected_data['max']:
            successful += 1
            total_error += abs(detected - expected_data['expected'])
    
    coverage = successful / len(expected_measurements) if expected_measurements else 0
    return params, results, successful, coverage, total_error


class RulerParameterOptimizer:
    def __init__(self, test_images_path):
        self.test_images_path = test_images_path
        self.expected_measurements = EXPECTED_MEASUREMENTS
        self.museum_selection = "Iraq Museum (Sippar Library)"
        self.cpu_count = mp.cpu_count()
        
    def diagnose(self):
        print("=== DIAGNOSTIC ===")
        for image_name, expected_data in self.expected_measurements.items():
            image_path = os.path.join(self.test_images_path, image_name)
            if not os.path.exists(image_path):
                continue
                
            try:
                detected = detect_1cm_distance_iraq(image_path, museum_selection=self.museum_selection)
                expected = expected_data['expected']
                min_val, max_val = expected_data['min'], expected_data['max']
                
                if detected is None:
                    status = "❌ NO DETECTION"
                elif min_val <= detected <= max_val:
                    status = f"✅ PASS ({abs(detected - expected):.0f}px error)"
                else:
                    status = f"❌ FAIL ({abs(detected - expected):.0f}px error)"
                
                print(f"{image_name}: {detected}px (expected {expected}px) - {status}")
                
            except Exception as e:
                print(f"{image_name}: ❌ ERROR - {e}")
    
    def generate_parameter_sets(self, num_sets):
        default_params = get_detection_parameters(self.museum_selection)
        param_ranges = {
            'hough_threshold': (10, 200),
            'hough_min_line_length': (10, 100),
            'hough_max_line_gap': (5, 50),
            'tick_max_width': (10, 40),
            'tick_min_width': (1, 15),
            'tick_min_height': (10, 80),
            'max_tick_thickness_px': (5, 40),
            'min_ticks_required': (6, 11),
            'consistency_threshold': (0.4, 1.0),
            'canny_low_threshold': (10, 50),
            'canny_high_threshold': (50, 150),
            'roi_height_fraction': (0.3, 0.8),
            'text_match_threshold': (0.3, 0.8)
        }
                
        fixed_params = {
            'num_ticks_for_1cm': 11
        }
        parameter_sets = []
        for _ in range(num_sets):
            params = fixed_params.copy()
            for param, (low, high) in param_ranges.items():
                if isinstance(default_params[param], float):
                    params[param] = round(random.uniform(low, high), 2)
                else:
                    params[param] = random.randint(int(low), int(high))
            parameter_sets.append(params)
        
        return parameter_sets
    
    def flexible_search(self, target_coverage=0.9, max_iterations=1000, use_multiprocessing=True):
        search_type = "PARALLEL" if use_multiprocessing else "SEQUENTIAL"
        print(f"=== {search_type} SEARCH ===")
        if use_multiprocessing:
            print(f"Using {self.cpu_count} CPU cores")
        print(f"Target: {target_coverage*100:.0f}% success rate over {max_iterations} iterations")
        
        best_coverage = 0
        best_params = None
        best_results = None
        start_time = time.time()
        iterations_completed = 0
        
        if use_multiprocessing:
            batch_size = self.cpu_count * 4
            
            while iterations_completed < max_iterations:
                current_batch_size = min(batch_size, max_iterations - iterations_completed)
                parameter_sets = self.generate_parameter_sets(current_batch_size)
                
                worker_args = [(params, self.test_images_path, self.expected_measurements, self.museum_selection) 
                              for params in parameter_sets]
                
                with ProcessPoolExecutor(max_workers=self.cpu_count) as executor:
                    future_to_params = {executor.submit(test_single_parameter_set, args): args[0] 
                                      for args in worker_args}
                    
                    for future in as_completed(future_to_params):
                        try:
                            params, results, successful, coverage, total_error = future.result()
                            iterations_completed += 1
                            
                            if coverage > best_coverage:
                                best_coverage = coverage
                                best_params = params
                                best_results = results
                                
                                print(f"*** NEW BEST! Iteration {iterations_completed}: {best_coverage*100:.1f}% success")
                                print(f"    Params: {params}")
                                
                                if best_coverage >= target_coverage:
                                    print(f"✅ Target achieved!")
                                    elapsed_time = time.time() - start_time
                                    self._print_final_results(best_coverage, elapsed_time, iterations_completed)
                                    return best_params, best_results, best_coverage
                            
                            if iterations_completed % 200 == 0:
                                elapsed = time.time() - start_time
                                rate = iterations_completed / elapsed if elapsed > 0 else 0
                                print(f"Progress: {iterations_completed}/{max_iterations} - Best: {best_coverage*100:.1f}% ({rate:.1f} iter/sec)")
                        
                        except Exception as e:
                            print(f"Error: {e}")
                            iterations_completed += 1
        else:
            for i in range(max_iterations):
                parameter_sets = self.generate_parameter_sets(1)
                worker_args = (parameter_sets[0], self.test_images_path, self.expected_measurements, self.museum_selection)
                
                try:
                    params, results, successful, coverage, total_error = test_single_parameter_set(worker_args)
                    iterations_completed += 1
                    
                    if coverage > best_coverage:
                        best_coverage = coverage
                        best_params = params
                        best_results = results
                        
                        print(f"*** NEW BEST! Iteration {iterations_completed}: {best_coverage*100:.1f}% success")
                        print(f"    Params: {params}")
                        
                        if best_coverage >= target_coverage:
                            print(f"✅ Target achieved!")
                            break
                    
                    if iterations_completed % 200 == 0:
                        elapsed = time.time() - start_time
                        rate = iterations_completed / elapsed if elapsed > 0 else 0
                        print(f"Progress: {iterations_completed}/{max_iterations} - Best: {best_coverage*100:.1f}% ({rate:.1f} iter/sec)")
                
                except Exception as e:
                    print(f"Error: {e}")
                    iterations_completed += 1
        
        elapsed_time = time.time() - start_time
        self._print_final_results(best_coverage, elapsed_time, iterations_completed)
        return best_params, best_results, best_coverage
    
    def _print_final_results(self, best_coverage, elapsed_time, iterations_completed):
        print(f"\nSearch complete: {elapsed_time/60:.1f}min, {iterations_completed} iterations")
        if best_coverage > 0:
            successful_images = int(best_coverage * len(self.expected_measurements))
            print(f"Best coverage: {successful_images}/{len(self.expected_measurements)} ({best_coverage*100:.1f}%)")
            rate = iterations_completed / elapsed_time if elapsed_time > 0 else 0
            print(f"Search rate: {rate:.1f} iterations/second")
        else:
            print("No successful parameter combination found.")
    
    def print_results(self, results, params):
        if not results:
            print("No results to display")
            return
        
        print(f"\nParameters: {params}")
        print("\nDetailed Results:")
        
        for image_name, detected in results.items():
            expected = self.expected_measurements[image_name]['expected']
            min_val, max_val = self.expected_measurements[image_name]['min'], self.expected_measurements[image_name]['max']
            
            if detected and min_val <= detected <= max_val:
                error = abs(detected - expected)
                print(f"✅ {image_name}: {detected}px (expected {expected}px, error {error:.1f}px)")
            else:
                print(f"❌ {image_name}: {detected}px (expected {expected}px)")


def main():
    parser = argparse.ArgumentParser(description="Ruler detection parameter optimization")
    parser.add_argument("--diagnose", action="store_true", help="Quick diagnostic")
    parser.add_argument("--flexible", action="store_true", help="Search for best parameters")
    parser.add_argument("--single-thread", action="store_true", help="Use single thread instead of multiprocessing")
    parser.add_argument("--target-coverage", type=float, default=0.9, help="Target success rate (default: 0.9)")
    parser.add_argument("--iterations", type=int, default=1000, help="Max iterations")
    
    args = parser.parse_args()
    
    test_images_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Examples", "Sippar")
    
    if not os.path.exists(test_images_path):
        print(f"ERROR: Test images directory not found: {test_images_path}")
        return
    
    print(f"Test images directory: {test_images_path}")
    optimizer = RulerParameterOptimizer(test_images_path)
    print(f"System has {optimizer.cpu_count} CPU cores available")
    
    if args.diagnose:
        optimizer.diagnose()
    elif args.flexible:
        use_mp = not args.single_thread
        best_params, results, coverage = optimizer.flexible_search(
            target_coverage=args.target_coverage, 
            max_iterations=args.iterations,
            use_multiprocessing=use_mp
        )
        if best_params:
            optimizer.print_results(results, best_params)
        else:
            print("No successful parameters found")
    else:
        print("No operation selected. Use --help for options.")
        print("\nRECOMMENDED:")
        print("  --diagnose              # See current performance (~30 sec)")
        print("  --flexible              # Multi-threaded search (FASTEST)")
        print("  --flexible --single-thread  # Single-threaded search")


if __name__ == "__main__":
    main()