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
            from vlm_validator.tools.validate_vlm import validate_vlm_output
            
            result = validate_vlm_output(
                vlm_output=vlm_output,
                frame_timestamps=frame_timestamps,
                skills_file=skills_file
            )
            
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