from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import logging
import os
from watsonx_credibility import WatsonxCredibilityScorer
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from watsonx_credibility import WatsonxCredibilityScorer

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Watsonx scorer
try:
    scorer = WatsonxCredibilityScorer()
    logger.info("Watsonx Credibility Scorer initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Watsonx scorer: {e}")
    scorer = None

# In-memory data store (replace with database in production)
data_store = {
    "items": [],
    "users": [],
    "sellers": [],
    "transactions": []
}

@app.route('/')
def home():
    """API Home endpoint"""
    return jsonify({
        "message": "Welcome to Logistics Hackathon API",
        "version": "1.0.0",
        "endpoints": {
            "GET /": "API information",
            "GET /health": "Health check",
            "GET /items": "Get all items",
            "GET /items/<id>": "Get specific item",
            "POST /items": "Create new item",
            "PUT /items/<id>": "Update item",
            "DELETE /items/<id>": "Delete item",
            "POST /seller/credibility": "Analyze seller credibility",
            "GET /seller/<id>/credibility": "Get seller credibility score",
            "POST /seller/register": "Register new seller",
            "GET /sellers": "Get all sellers"
        }
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    watsonx_status = "connected" if scorer else "not configured"
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "watsonx_status": watsonx_status
    }), 200

@app.route('/items', methods=['GET'])
def get_items():
    """Get all items"""
    return jsonify({
        "success": True,
        "count": len(data_store["items"]),
        "data": data_store["items"]
    }), 200

@app.route('/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    """Get specific item by ID"""
    item = next((item for item in data_store["items"] if item["id"] == item_id), None)
    
    if item:
        return jsonify({
            "success": True,
            "data": item
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": "Item not found"
        }), 404

@app.route('/items', methods=['POST'])
def create_item():
    """Create a new item"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'name' not in data:
            return jsonify({
                "success": False,
                "error": "Name is required"
            }), 400
        
        # Create new item
        new_item = {
            "id": len(data_store["items"]) + 1,
            "name": data["name"],
            "description": data.get("description", ""),
            "created_at": datetime.now().isoformat()
        }
        
        data_store["items"].append(new_item)
        logger.info(f"Created item: {new_item['id']}")
        
        return jsonify({
            "success": True,
            "message": "Item created successfully",
            "data": new_item
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    """Update an existing item"""
    try:
        data = request.get_json()
        item = next((item for item in data_store["items"] if item["id"] == item_id), None)
        
        if not item:
            return jsonify({
                "success": False,
                "error": "Item not found"
            }), 404
        
        # Update item fields
        item["name"] = data.get("name", item["name"])
        item["description"] = data.get("description", item["description"])
        item["updated_at"] = datetime.now().isoformat()
        
        logger.info(f"Updated item: {item_id}")
        
        return jsonify({
            "success": True,
            "message": "Item updated successfully",
            "data": item
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating item: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Delete an item"""
    global data_store
    
    item = next((item for item in data_store["items"] if item["id"] == item_id), None)
    
    if not item:
        return jsonify({
            "success": False,
            "error": "Item not found"
        }), 404
    
    data_store["items"] = [item for item in data_store["items"] if item["id"] != item_id]
    logger.info(f"Deleted item: {item_id}")
    
    return jsonify({
        "success": True,
        "message": "Item deleted successfully"
    }), 200

# ============= SELLER CREDIBILITY ENDPOINTS =============

@app.route('/seller/register', methods=['POST'])
def register_seller():
    """Register a new seller"""
    try:
        data = request.get_json()
        
        if not data or 'seller_name' not in data:
            return jsonify({
                "success": False,
                "error": "Seller name is required"
            }), 400
        
        new_seller = {
            "seller_id": f"SELL_{len(data_store['sellers']) + 1:05d}",
            "seller_name": data["seller_name"],
            "seller_since": datetime.now().isoformat(),
            "total_sales": 0,
            "average_transaction_value": 0,
            "reviews": [],
            "dispute_rate": 0,
            "on_time_rate": 1.0,
            "avg_response_hours": 24,
            "verified": data.get("verified", False),
            "created_at": datetime.now().isoformat()
        }
        
        data_store["sellers"].append(new_seller)
        logger.info(f"Registered seller: {new_seller['seller_id']}")
        
        return jsonify({
            "success": True,
            "message": "Seller registered successfully",
            "data": new_seller
        }), 201
        
    except Exception as e:
        logger.error(f"Error registering seller: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/sellers', methods=['GET'])
def get_sellers():
    """Get all sellers"""
    return jsonify({
        "success": True,
        "count": len(data_store["sellers"]),
        "data": data_store["sellers"]
    }), 200

@app.route('/seller/<seller_id>/credibility', methods=['GET'])
def get_seller_credibility(seller_id):
    """Get credibility score for a specific seller"""
    try:
        # Check if Watsonx is configured
        if not scorer:
            return jsonify({
                "success": False,
                "error": "Watsonx credibility scorer not configured. Please set IBM_API_KEY and IBM_PROJECT_ID"
            }), 503
        
        # Find seller
        seller = next((s for s in data_store["sellers"] if s["seller_id"] == seller_id), None)
        
        if not seller:
            return jsonify({
                "success": False,
                "error": "Seller not found"
            }), 404
        
        # Generate credibility score
        logger.info(f"Analyzing credibility for seller: {seller_id}")
        result = scorer.generate_credibility_score(seller)
        stamp = scorer.get_stamp_approval(result['credibility_score'])
        
        return jsonify({
            "success": True,
            "seller_id": seller_id,
            "credibility": result,
            "stamp": stamp
        }), 200
        
    except Exception as e:
        logger.error(f"Error analyzing seller credibility: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/seller/credibility', methods=['POST'])
def analyze_seller_credibility():
    """Analyze seller credibility with custom data"""
    try:
        # Check if Watsonx is configured
        if not scorer:
            return jsonify({
                "success": False,
                "error": "Watsonx credibility scorer not configured. Please set IBM_API_KEY and IBM_PROJECT_ID"
            }), 503
        
        seller_data = request.get_json()
        
        if not seller_data:
            return jsonify({
                "success": False,
                "error": "Seller data is required"
            }), 400
        
        # Validate required fields
        required_fields = ['seller_id', 'seller_since', 'total_sales']
        missing_fields = [field for field in required_fields if field not in seller_data]
        
        if missing_fields:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        # Generate credibility score
        logger.info(f"Analyzing credibility for seller: {seller_data['seller_id']}")
        result = scorer.generate_credibility_score(seller_data)
        stamp = scorer.get_stamp_approval(result['credibility_score'])
        
        return jsonify({
            "success": True,
            "credibility": result,
            "stamp": stamp
        }), 200
        
    except Exception as e:
        logger.error(f"Error analyzing seller credibility: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/seller/<seller_id>/update', methods=['PUT'])
def update_seller(seller_id):
    """Update seller information"""
    try:
        data = request.get_json()
        seller = next((s for s in data_store["sellers"] if s["seller_id"] == seller_id), None)
        
        if not seller:
            return jsonify({
                "success": False,
                "error": "Seller not found"
            }), 404
        
        # Update seller fields
        updatable_fields = ['total_sales', 'average_transaction_value', 'dispute_rate', 
                          'on_time_rate', 'avg_response_hours', 'verified']
        
        for field in updatable_fields:
            if field in data:
                seller[field] = data[field]
        
        # Add review if provided
        if 'review' in data:
            seller['reviews'].append(data['review'])
        
        seller['updated_at'] = datetime.now().isoformat()
        logger.info(f"Updated seller: {seller_id}")
        
        return jsonify({
            "success": True,
            "message": "Seller updated successfully",
            "data": seller
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating seller: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/demo/create-sample-sellers', methods=['POST'])
def create_sample_sellers():
    """Create sample sellers for demo purposes"""
    try:
        sample_sellers = [
            {
                "seller_id": "SELL_00001",
                "seller_name": "TechSupplies Co",
                "seller_since": "2023-01-15T00:00:00Z",
                "total_sales": 487,
                "average_transaction_value": 1250.50,
                "reviews": [
                    {"rating": 5, "comment": "Excellent service, fast shipping!"},
                    {"rating": 5, "comment": "Great quality products"},
                    {"rating": 4, "comment": "Good seller, slight delay"},
                    {"rating": 5, "comment": "Professional and responsive"}
                ],
                "dispute_rate": 0.02,
                "on_time_rate": 0.94,
                "avg_response_hours": 3.5,
                "verified": True,
                "created_at": datetime.now().isoformat()
            },
            {
                "seller_id": "SELL_00002",
                "seller_name": "FastShip Logistics",
                "seller_since": "2024-06-10T00:00:00Z",
                "total_sales": 89,
                "average_transaction_value": 450.25,
                "reviews": [
                    {"rating": 3, "comment": "Okay service"},
                    {"rating": 4, "comment": "Decent quality"},
                    {"rating": 2, "comment": "Delayed shipment"}
                ],
                "dispute_rate": 0.12,
                "on_time_rate": 0.76,
                "avg_response_hours": 18,
                "verified": False,
                "created_at": datetime.now().isoformat()
            }
        ]
        
        data_store["sellers"].extend(sample_sellers)
        
        return jsonify({
            "success": True,
            "message": f"Created {len(sample_sellers)} sample sellers",
            "data": sample_sellers
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating sample sellers: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)