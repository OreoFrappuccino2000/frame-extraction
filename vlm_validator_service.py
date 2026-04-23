import os
import sys
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add vlm_validator to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "vlm_validator",
        "version": "1.0.0"
    })

@app.route('/info', methods=['GET'])
def service_info():
    """Service information endpoint"""
    return jsonify({
        "name": "VLM Validator Service",
        "description": "HTTP wrapper for VLM Validator Plugin",
        "endpoints": [
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/info", "method": "GET", "description": "Service information"},
            {"path": "/validate", "method": "POST", "description": "Validate VLM output"}
        ]
    })

@app.route('/validate', methods=['POST'])
def validate_vlm():
    """
    Validate VLM output using the vlm_validator plugin
    
    Expected JSON payload:
    {
        "vlm_output": {...},  # VLM output JSON
        "frame_timestamps": [...],  # Frame timestamps
        "skills_file": "skills.md"  # Optional skills file
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400
        
        vlm_output = data.get("vlm_output")
        frame_timestamps = data.get("frame_timestamps", [])
        skills_file = data.get("skills_file", "skills.md")
        
        if not vlm_output:
            return jsonify({
                "success": False,
                "error": "Missing required field: vlm_output"
            }), 400
        
        # Import and use the vlm_validator
        try:
            # Import the validate_vlm module directly
            import sys
            import os
            
            # Add vlm_validator tools directory to path
            tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlm_validator", "tools")
            if tools_dir not in sys.path:
                sys.path.insert(0, tools_dir)
            
            # Import the validation functions
            from validate_vlm import _l1_clean_events, _l2_esports_validate, _optimize_for_short_video, _analyze_intents
            
            # Build ground truth map from frame timestamps
            def _build_gt_map(frames):
                return {frame.get("frame_index", i): frame.get("video_time", 0.0) 
                       for i, frame in enumerate(frames)}
            
            # Process the VLM output using the validation pipeline
            gt_map = _build_gt_map(frame_timestamps)
            
            # L1: Basic cleaning
            events = _l1_clean_events(vlm_output.get("events", []), gt_map)
            
            # L2: E-sports validation
            events = _l2_esports_validate(events)
            
            # L3: Short video optimization
            events = _optimize_for_short_video(events)
            
            # Intent analysis
            intent_analysis = _analyze_intents(events)
            
            # Build result
            result = {
                "events": events,
                "views": vlm_output.get("views", []),
                "metrics": vlm_output.get("metrics", []),
                "squads": vlm_output.get("squads", []),
                "intent_analysis": intent_analysis,
                "stats": {
                    "input_events": len(vlm_output.get("events", [])),
                    "output_events": len(events),
                    "dropped_events": len(vlm_output.get("events", [])) - len(events)
                }
            }
            
            return jsonify({
                "success": True,
                "result": result
            })
            
        except ImportError as e:
            logger.error(f"Failed to import vlm_validator: {e}")
            return jsonify({
                "success": False,
                "error": f"VLM validator module not available: {str(e)}"
            }), 500
            
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)