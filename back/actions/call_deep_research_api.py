import json
import subprocess
import tempfile
import time
import os
from typing import Optional

def run_research_api(query: str, breadth: int = 3, depth: int = 3) -> Optional[str]:
    """
    Most reliable method using curl to handle large responses.

    This bypasses Python's requests library issues with buffered responses.
    """
    url = "http://34.30.168.182/api/research"

    payload = json.dumps({
        "query": query,
        "breadth": breadth,
        "depth": depth
    })

    print(f"[INFO] Starting deep research API call using curl")
    print(f"[INFO] Parameters: breadth={breadth}, depth={depth}")
    print(f"[INFO] Query: {query[:100]}..." if len(query) > 100 else f"[INFO] Query: {query}")

    # Write payload to temporary file (curl handles this better than inline JSON)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(payload)
        temp_file = f.name

    try:
        # Calculate timeout based on complexity
        timeout = max(300, 60 * breadth * depth)  # At least 5 min, or 60s per breadth*depth
        print(f"[INFO] Using timeout of {timeout} seconds ({timeout//60} minutes)")

        # Build curl command with all necessary flags
        cmd = [
            'curl',
            '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '-H', 'Connection: close',
            '-H', 'Accept: application/json',
            '-d', f'@{temp_file}',
            '--max-time', str(timeout),
            '--connect-timeout', '30',
            '--no-buffer',         # Disable output buffering
            '--no-keepalive',      # Disable keep-alive
            '--tcp-nodelay',       # Disable Nagle's algorithm
            '-s',                  # Silent mode (no progress bar)
            '-S',                  # Show errors
            '--compressed',        # Handle gzip/deflate if server uses it
            url
        ]

        print(f"[INFO] Sending request to API...")
        print(f"[INFO] This may take up to {timeout//60} minutes. Please wait...")
        start_time = time.time()

        # Execute curl with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 60  # Add buffer to subprocess timeout
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            print(f"[SUCCESS] Response received in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

            # Check if we got any output
            if not result.stdout:
                print(f"[ERROR] Empty response from server")
                return None

            # Try to parse JSON response
            try:
                data = json.loads(result.stdout)

                if data.get("success"):
                    # Extract metadata if available
                    metadata = data.get("metadata", {})
                    print(f"[SUCCESS] Research completed successfully!")

                    if metadata:
                        print(f"[INFO] Processing time: {metadata.get('processingTime', 'N/A')}ms")
                        print(f"[INFO] Request ID: {metadata.get('requestId', 'N/A')}")

                        # Check if optimized response
                        if metadata.get('responseOptimized'):
                            print(f"[INFO] Total learnings: {metadata.get('totalLearnings', 'N/A')}")
                            print(f"[INFO] Total URLs: {metadata.get('totalUrls', 'N/A')}")
                        else:
                            print(f"[INFO] Learnings: {metadata.get('learningsCount', 'N/A')}")
                            print(f"[INFO] URLs: {metadata.get('urlsCount', 'N/A')}")

                    answer = data.get("answer")
                    if answer:
                        print(f"[INFO] Answer length: {len(answer)} characters")
                        return answer
                    else:
                        print(f"[WARNING] Success but no answer in response")
                        return None
                else:
                    # API returned an error
                    error_msg = data.get('error', 'Unknown error')
                    error_code = data.get('code', 'UNKNOWN')
                    print(f"[ERROR] API error: {error_msg} (Code: {error_code})")

                    if 'details' in data:
                        print(f"[ERROR] Details: {data['details']}")

                    return None

            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON response: {e}")
                print(f"[DEBUG] Raw response (first 1000 chars): {result.stdout[:1000]}")

                # Check if it might be HTML error page
                if result.stdout.startswith('<!DOCTYPE') or result.stdout.startswith('<html'):
                    print(f"[ERROR] Received HTML instead of JSON (possibly an error page)")

                return None
        else:
            # Curl failed
            print(f"[ERROR] Curl failed with exit code {result.returncode} after {elapsed:.1f}s")

            # Interpret common curl exit codes
            error_messages = {
                6: "Couldn't resolve host",
                7: "Failed to connect to host",
                28: "Operation timeout",
                35: "SSL connection error",
                52: "Server returned empty response",
                56: "Failure receiving data"
            }

            if result.returncode in error_messages:
                print(f"[ERROR] {error_messages[result.returncode]}")

            if result.stderr:
                print(f"[ERROR] Curl stderr: {result.stderr}")

            return None

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"[ERROR] Request timed out after {elapsed:.1f} seconds")
        print(f"[INFO] The research might still be running on the server")
        return None

    except FileNotFoundError:
        print(f"[ERROR] curl command not found. Please install curl:")
        print(f"  Ubuntu/Debian: sudo apt-get install curl")
        print(f"  MacOS: brew install curl")
        print(f"  Windows: Download from https://curl.se/windows/")
        return None

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        # Clean up temporary file
        if 'temp_file' in locals() and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass


def test_connectivity():
    """Test basic connectivity to the API using curl."""
    url = "http://34.30.168.182/health"

    try:
        print(f"[TEST] Checking API health...")
        result = subprocess.run(
            ['curl', '-s', '--max-time', '5', url],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                status = data.get('status', 'unknown')
                print(f"[TEST] API health check: {status}")
                return status == 'healthy'
            except:
                print(f"[TEST] Health check response: {result.stdout[:100]}")
                return 'healthy' in result.stdout.lower()
        else:
            print(f"[TEST] Health check failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"[TEST] Health check error: {e}")
        return False


if __name__ == "__main__":
    # First test connectivity
    if test_connectivity():
        print(f"[INFO] API is reachable\n")

        # Test with production parameters
        query = "What are the latest developments in quantum computing and AI?"

        # Start with moderate parameters
        print("=" * 60)
        print("Test 1: Moderate complexity (breadth=3, depth=3)")
        print("=" * 60)
        result = run_research_api(query, breadth=3, depth=3)

        if result:
            print(f"\n✓ Success!")
            print(f"Answer preview: {result[:500]}...")
        else:
            print(f"\n✗ Failed with moderate parameters")

        # If you want to test with high complexity
        print("\n" + "=" * 60)
        print("Test 2: High complexity (breadth=6, depth=4)")
        print("=" * 60)
        result = run_research_api(query, breadth=6, depth=4)

        if result:
            print(f"\n✓ Success!")
            print(f"Answer preview: {result[:500]}...")
        else:
            print(f"\n✗ Failed with high complexity parameters")
            print(f"[INFO] Consider reducing breadth/depth for this query")
    else:
        print(f"[ERROR] API is not reachable. Please check the service status.")
