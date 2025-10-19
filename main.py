"""
Innovation Hackathon - Logistics Rating System
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the Watsonx credibility scorer
try:
    from watsonx_credibility import WatsonxCredibilityScorer
    WATSONX_AVAILABLE = True
except ImportError:
    WATSONX_AVAILABLE = False
    logging.warning("Watsonx credibility module not available")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration class for project settings"""
    app_name: str = "Logistics Rating Hackathon"
    version: str = "1.0.0"
    debug: bool = True
    data_dir: str = "data"
    output_dir: str = "output"
    models_dir: str = "models"
    
    def __post_init__(self):
        """Create necessary directories"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)


class DataManager:
    """Handles data loading, saving, and processing"""
    
    def __init__(self, config: Config):
        self.config = config
        
    def load_json(self, filename: str) -> Dict:
        """Load JSON data from file"""
        filepath = os.path.join(self.config.data_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded data from {filename}")
            return data
        except FileNotFoundError:
            logger.warning(f"File {filename} not found")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {filename}")
            return {}
    
    def save_json(self, data: Dict, filename: str) -> bool:
        """Save data to JSON file"""
        filepath = os.path.join(self.config.output_dir, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved data to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")
            return False
    
    def process_seller_data(self, sellers: List[Dict]) -> List[Dict]:
        """Process and enrich seller data"""
        processed = []
        for seller in sellers:
            # Add calculated fields
            if 'reviews' in seller and seller['reviews']:
                avg_rating = sum(r.get('rating', 0) for r in seller['reviews']) / len(seller['reviews'])
                seller['avg_rating'] = round(avg_rating, 2)
            else:
                seller['avg_rating'] = 0
            
            processed.append(seller)
        
        logger.info(f"Processed {len(processed)} seller records")
        return processed
    
    def generate_sample_sellers(self, count: int = 5) -> List[Dict]:
        """Generate sample seller data for testing"""
        import random
        from datetime import timedelta
        
        sample_names = [
            "TechSupplies Co", "FastShip Logistics", "Global Traders Inc",
            "QuickDeliver Express", "Reliable Goods Ltd", "Prime Suppliers",
            "Elite Commerce", "Swift Logistics", "MegaMart Sellers", "ProShip Co"
        ]
        
        sample_reviews = [
            {"rating": 5, "comment": "Excellent service, fast shipping!"},
            {"rating": 5, "comment": "Great quality products, will buy again"},
            {"rating": 4, "comment": "Good seller, slight delay in shipping"},
            {"rating": 5, "comment": "Professional and responsive"},
            {"rating": 4, "comment": "Product as described"},
            {"rating": 3, "comment": "Average experience"},
            {"rating": 2, "comment": "Delayed delivery"},
            {"rating": 5, "comment": "Perfect transaction"}
        ]
        
        sellers = []
        for i in range(count):
            # Random account age (1-24 months)
            months_old = random.randint(1, 24)
            seller_since = datetime.now() - timedelta(days=months_old * 30)
            
            # Random metrics
            total_sales = random.randint(10, 500)
            num_reviews = random.randint(3, 8)
            
            seller = {
                "seller_id": f"SELL_{i+1:05d}",
                "seller_name": sample_names[i % len(sample_names)],
                "seller_since": seller_since.isoformat(),
                "total_sales": total_sales,
                "average_transaction_value": round(random.uniform(100, 2000), 2),
                "reviews": random.sample(sample_reviews, num_reviews),
                "dispute_rate": round(random.uniform(0, 0.15), 3),
                "on_time_rate": round(random.uniform(0.7, 1.0), 3),
                "avg_response_hours": round(random.uniform(1, 48), 1),
                "verified": random.choice([True, False])
            }
            
            sellers.append(seller)
        
        return sellers


class CredibilityAnalyzer:
    """Handles seller credibility analysis"""
    
    def __init__(self, config: Config):
        self.config = config
        self.scorer = None
        
        if WATSONX_AVAILABLE:
            try:
                self.scorer = WatsonxCredibilityScorer()
                logger.info("Watsonx Credibility Scorer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Watsonx scorer: {e}")
                logger.info("Running without Watsonx integration")
    
    def analyze_seller(self, seller_data: Dict) -> Dict:
        """Analyze a single seller and return credibility score"""
        if self.scorer:
            try:
                result = self.scorer.generate_credibility_score(seller_data)
                stamp = self.scorer.get_stamp_approval(result['credibility_score'])
                return {
                    "credibility": result,
                    "stamp": stamp,
                    "analysis_method": "watsonx_ai"
                }
            except Exception as e:
                logger.error(f"Error in Watsonx analysis: {e}")
                return self._fallback_analysis(seller_data)
        else:
            return self._fallback_analysis(seller_data)
    
    def _fallback_analysis(self, seller_data: Dict) -> Dict:
        """Simple rule-based credibility scoring as fallback"""
        score = 50  # Base score
        
        # Adjust based on metrics
        total_sales = seller_data.get('total_sales', 0)
        if total_sales > 300:
            score += 20
        elif total_sales > 100:
            score += 10
        
        on_time_rate = seller_data.get('on_time_rate', 0.5)
        score += (on_time_rate - 0.5) * 40
        
        dispute_rate = seller_data.get('dispute_rate', 0.1)
        score -= dispute_rate * 100
        
        verified = seller_data.get('verified', False)
        if verified:
            score += 10
        
        # Clamp between 0-100
        score = max(0, min(100, score))
        
        # Determine stamp
        if score >= 80:
            stamp = {"stamp": "APPROVED", "color": "green", "message": "Reliable Seller"}
        elif score >= 60:
            stamp = {"stamp": "CAUTION", "color": "yellow", "message": "Proceed with Caution"}
        else:
            stamp = {"stamp": "HIGH_RISK", "color": "red", "message": "Not Recommended"}
        
        return {
            "credibility": {
                "seller_id": seller_data.get('seller_id'),
                "credibility_score": round(score, 2),
                "risk_level": "low" if score >= 80 else "medium" if score >= 60 else "high",
                "recommendation": "approve" if score >= 80 else "review" if score >= 60 else "reject",
                "summary": "Rule-based credibility assessment"
            },
            "stamp": stamp,
            "analysis_method": "rule_based_fallback"
        }
    
    def batch_analyze_sellers(self, sellers: List[Dict]) -> List[Dict]:
        """Analyze multiple sellers"""
        results = []
        for seller in sellers:
            analysis = self.analyze_seller(seller)
            results.append({
                "seller_id": seller.get('seller_id'),
                "seller_name": seller.get('seller_name'),
                **analysis
            })
        return results


class Application:
    """Main application class"""
    
    def __init__(self, config: Config):
        self.config = config
        self.data_manager = DataManager(config)
        self.credibility_analyzer = CredibilityAnalyzer(config)
        logger.info(f"Initialized {config.app_name} v{config.version}")
    
    def run(self):
        """Main application logic"""
        logger.info("Starting application...")
        
        try:
            # 1. Load or generate seller data
            sellers_data = self.data_manager.load_json("sellers.json")
            
            if not sellers_data or 'sellers' not in sellers_data:
                logger.info("No seller data found, generating samples...")
                sellers = self.data_manager.generate_sample_sellers(5)
                sellers_data = {"sellers": sellers}
                self.data_manager.save_json(sellers_data, "sellers.json")
            else:
                sellers = sellers_data['sellers']
            
            # 2. Process seller data
            processed_sellers = self.data_manager.process_seller_data(sellers)
            
            # 3. Analyze credibility
            logger.info("Analyzing seller credibility...")
            credibility_results = self.credibility_analyzer.batch_analyze_sellers(processed_sellers)
            
            # 4. Generate final report
            report = {
                "timestamp": datetime.now().isoformat(),
                "total_sellers": len(processed_sellers),
                "analysis_method": credibility_results[0]['analysis_method'] if credibility_results else "none",
                "results": credibility_results
            }
            
            # 5. Save results
            self.data_manager.save_json(report, "credibility_report.json")
            
            logger.info("Application completed successfully")
            return report
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            raise
    
    def demo_mode(self):
        """Run a demo with sample data"""
        logger.info("Running in demo mode...")
        
        # Generate sample sellers
        sample_sellers = self.data_manager.generate_sample_sellers(5)
        
        # Save to data directory
        sellers_data = {"sellers": sample_sellers}
        self.data_manager.save_json(sellers_data, "../data/sellers.json")
        
        # Run analysis
        return self.run()


def print_report_summary(report: Dict):
    """Print a formatted summary of the report"""
    print(f"\n{'='*70}")
    print(f"🚀 {report.get('total_sellers', 0)} SELLERS ANALYZED")
    print(f"{'='*70}")
    print(f"Analysis Method: {report.get('analysis_method', 'unknown').upper()}")
    print(f"Timestamp: {report.get('timestamp', 'N/A')}")
    print(f"{'='*70}\n")
    
    for result in report.get('results', []):
        credibility = result.get('credibility', {})
        stamp = result.get('stamp', {})
        
        print(f"Seller: {result.get('seller_name', 'Unknown')} ({result.get('seller_id', 'N/A')})")
        print(f"  Score: {credibility.get('credibility_score', 0)}/100")
        print(f"  {stamp.get('badge', '')} Stamp: {stamp.get('stamp', 'N/A')} - {stamp.get('message', '')}")
        print(f"  Risk: {credibility.get('risk_level', 'unknown').upper()}")
        print(f"  Recommendation: {credibility.get('recommendation', 'review').upper()}")
        print()
    
    print(f"{'='*70}")
    print(f"✅ Full report saved to 'output/credibility_report.json'")
    print(f"{'='*70}\n")


def main():
    """Entry point"""
    # Initialize configuration
    config = Config()
    
    # Create and run application
    app = Application(config)
    
    # Run demo mode
    report = app.demo_mode()
    
    # Print summary
    print_report_summary(report)


if __name__ == "__main__":
    main()