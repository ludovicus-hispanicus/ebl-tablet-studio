import re
import time


def print_final_statistics(start_time, total_ok, total_err, cr2_conv_total, failed_objects):
    """Print final processing statistics with detailed failure reasons."""
    end_time = time.time()
    elapsed_seconds = end_time - start_time
    minutes, seconds = divmod(elapsed_seconds, 60)

    avg_seconds = elapsed_seconds / total_ok if total_ok > 0 else 0
    avg_minutes, avg_seconds = divmod(avg_seconds, 60)

    print(f"\n{'=' * 60}")
    print(f"PROCESSING SUMMARY")
    print(f"{'=' * 60}")
    print(f"Time elapsed: {int(minutes):02d}m {int(seconds):02d}s")
    print(f"RAW converted: {cr2_conv_total}")
    print(f"Processed OK: {total_ok}")
    print(f"Failed: {total_err}")
    if total_ok > 0:
        print(f"Average time per object: {int(avg_minutes):02d}m {int(avg_seconds):02d}s")

    try:
        from lens_correction_hint import report_summary
        for line in report_summary():
            print(line)
    except Exception:
        pass

    if total_err > 0:
        print(f"\n--- FAILED TABLETS ---")
        for obj in failed_objects:
            if isinstance(obj, dict):
                name = obj.get('name', 'unknown')
                reason = obj.get('reason', 'Unknown error')
                print(f"  {name}: {reason}")
            else:
                # Backward compatibility: plain string
                print(f"  {obj}")

    print(f"{'=' * 60}\n")
