import requests
import json
import sys

def test_vlm_validator_service(base_url="http://localhost:5000"):
    """Test the VLM validator service endpoints"""
    
    print("=== Testing VLM Validator Service ===\n")
    
    # Test health endpoint
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✓ Health endpoint OK")
            print(f"   Response: {response.json()}")
        else:
            print(f"✗ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health endpoint error: {e}")
        return False
    
    # Test info endpoint
    print("\n2. Testing info endpoint...")
    try:
        response = requests.get(f"{base_url}/info")
        if response.status_code == 200:
            print("✓ Info endpoint OK")
            print(f"   Service: {response.json()['name']}")
        else:
            print(f"✗ Info endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Info endpoint error: {e}")
        return False
    
    # Test validation endpoint with sample data
    print("\n3. Testing validation endpoint...")
    
    sample_vlm_output = {
        "events": [
            {
                "k": 1,
                "video_time": 0.0,
                "type": "player_elimination",
                "actor": "MAD LEMON",
                "team": "MAD",
                "target": None,
                "target_team": None,
                "weapon": "frag_grenade",
                "damage_type": "frag",
                "text": "GRENADE ELIMINATION MAD LEMON",
                "position_tag": "roof",
                "confidence": 0.95,
                "evidence_k": [1, 2]
            }
        ],
        "views": [
            {
                "k": 1,
                "video_time": 0.0,
                "camera_mode": "observer",
                "pov_confirmed": False,
                "observer_mode": True
            }
        ],
        "metrics": [
            {
                "k": 1,
                "video_time": 0.0,
                "alive": 62,
                "teams": 16,
                "phase": 1,
                "zone_timer_s": None
            }
        ],
        "squads": []
    }
    
    sample_frame_timestamps = [
        {"frame_index": 1, "timestamp_seconds": 0.0, "video_time": 0.0, "timestamp_formatted": "00:00:00.000"}
    ]
    
    payload = {
        "vlm_output": sample_vlm_output,
        "frame_timestamps": sample_frame_timestamps,
        "skills_file": "skills.md"
    }
    
    try:
        response = requests.post(
            f"{base_url}/validate",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✓ Validation endpoint OK")
                print(f"   Validation result received")
                
                # Print validation stats if available
                if "result" in result and "stats" in result["result"]:
                    stats = result["result"]["stats"]
                    print(f"   Input events: {stats.get('input_events', 0)}")
                    print(f"   Output events: {stats.get('output_events', 0)}")
                    print(f"   Dropped events: {stats.get('dropped_events', 0)}")
            else:
                print(f"✗ Validation failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"✗ Validation endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Validation endpoint error: {e}")
        return False
    
    print("\n=== All tests passed! ===")
    return True

if __name__ == "__main__":
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    success = test_vlm_validator_service(base_url)
    
    if not success:
        print("\n=== Some tests failed ===")
        sys.exit(1)