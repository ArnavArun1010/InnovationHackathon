"""
IBM Watsonx Seller Credibility Scoring Module

This module uses IBM Watsonx AI to generate credibility scores for sellers
based on their historical data and reviews.
"""

import os
import json
from datetime import datetime
from ibm_watson_machine_learning.foundation_models import Model
from ibm_watson_machine_learning.metanames import GenTextParamsMetaNames as GenParams
from ibm_watson_machine_learning.foundation_models.utils.enums import ModelTypes

class WatsonxCredibilityScorer:
    def __init__(self, api_key=None, project_id=None, url=None):
        """
        Initialize Watsonx connection
        
        Args:
            api_key: IBM Cloud API key (or set IBM_API_KEY env var)
            project_id: Watsonx project ID (or set IBM_PROJECT_ID env var)
            url: Watsonx URL (or set IBM_URL env var, defaults to us-south)
        """
        self.api_key = api_key or os.getenv('IBM_API_KEY')
        self.project_id = project_id or os.getenv('IBM_PROJECT_ID')
        self.url = url or os.getenv('IBM_URL', 'https://us-south.ml.cloud.ibm.com')
        
        if not self.api_key or not self.project_id:
            raise ValueError("IBM_API_KEY and IBM_PROJECT_ID must be provided or set as environment variables")
        
        # Initialize model credentials
        self.credentials = {
            "url": self.url,
            "apikey": self.api_key
        }
        
        # Model parameters - optimized for structured output
        self.model_params = {
            GenParams.DECODING_METHOD: "greedy",
            GenParams.MAX_NEW_TOKENS: 800,
            GenParams.MIN_NEW_TOKENS: 100,
            GenParams.TEMPERATURE: 0.5,
            GenParams.TOP_K: 50,
            GenParams.TOP_P: 0.95,
            GenParams.REPETITION_PENALTY: 1.1
        }
        
        # Initialize the model (using Llama 3.3 70B for best performance)
        # Alternative options: meta-llama/llama-3-1-8b (faster), ibm/granite-3-8b-instruct
        self.model = Model(
            model_id="meta-llama/llama-3-3-70b-instruct",
            params=self.model_params,
            credentials=self.credentials,
            project_id=self.project_id
        )
    
    def _format_reviews_summary(self, reviews):
        """Format reviews into a readable summary"""
        if not reviews:
            return "No reviews available."
        
        summary = f"Total reviews: {len(reviews)}\n"
        
        # Sample recent reviews
        recent = reviews[:5] if len(reviews) > 5 else reviews
        summary += "Recent feedback:\n"
        for i, review in enumerate(recent, 1):
            rating = review.get('rating', 'N/A')
            comment = review.get('comment', 'No comment')
            summary += f"{i}. Rating: {rating}/5 - {comment}\n"
        
        return summary
    
    def _calculate_tenure_months(self, seller_since):
        """Calculate how long seller has been active"""
        if isinstance(seller_since, str):
            seller_since = datetime.fromisoformat(seller_since.replace('Z', '+00:00'))
        
        months = (datetime.now() - seller_since).days / 30
        return round(months, 1)
    
    def _build_prompt(self, seller_data):
        """Build the prompt for Watsonx"""
        
        tenure_months = self._calculate_tenure_months(
            seller_data.get('seller_since', datetime.now())
        )
        
        reviews_summary = self._format_reviews_summary(
            seller_data.get('reviews', [])
        )
        
        # Calculate average rating
        reviews = seller_data.get('reviews', [])
        avg_rating = sum(r.get('rating', 0) for r in reviews) / len(reviews) if reviews else 0
        
        # Calculate transaction scale
        total_sales = seller_data.get('total_sales', 0)
        avg_transaction = seller_data.get('average_transaction_value', 0)
        total_volume = total_sales * avg_transaction
        
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert financial analyst evaluating seller credibility for a logistics platform. Analyze the data carefully and provide detailed, specific insights based on the actual metrics provided.<|eot_id|><|start_header_id|>user<|end_header_id|>

Analyze this seller and provide a credibility score from 0-100:

SELLER PROFILE:
- Seller ID: {seller_data.get('seller_id', 'Unknown')}
- Business Name: {seller_data.get('seller_name', 'Unknown')}
- Account Age: {tenure_months} months
- Total Completed Sales: {total_sales}
- Average Order Value: ${avg_transaction:,.2f}
- Total Transaction Volume: ${total_volume:,.2f}
- Average Customer Rating: {avg_rating:.2f}/5.0 stars
- Number of Reviews: {len(reviews)}

PERFORMANCE METRICS:
- Dispute Rate: {seller_data.get('dispute_rate', 0)*100:.1f}% (lower is better)
- On-time Delivery Rate: {seller_data.get('on_time_rate', 0)*100:.1f}% (higher is better)
- Average Response Time: {seller_data.get('avg_response_hours', 24):.1f} hours
- Identity Verified: {'Yes' if seller_data.get('verified', False) else 'No'}

CUSTOMER REVIEWS:
{reviews_summary}

ANALYSIS INSTRUCTIONS:
1. Calculate a credibility score (0-100) based on ALL the data above
2. Identify 3 SPECIFIC strengths from the actual data (not generic statements)
3. Identify 2 SPECIFIC concerns from the actual data (not generic statements)
4. Consider account age, sales volume, delivery performance, and customer feedback
5. Be specific - mention actual numbers and metrics in your analysis

IMPORTANT: Base your analysis on the ACTUAL DATA provided. Do not use generic phrases like "Limited data available" when there are {len(reviews)} reviews and {total_sales} sales.

Provide your analysis in this EXACT JSON format:
{{
    "credibility_score": <number between 0-100>,
    "risk_level": "<low or medium or high>",
    "key_strengths": [
        "First specific strength with actual metrics",
        "Second specific strength with actual metrics", 
        "Third specific strength with actual metrics"
    ],
    "key_concerns": [
        "First specific concern with actual metrics",
        "Second specific concern with actual metrics"
    ],
    "recommendation": "<approve or review or reject>",
    "confidence": "<high or medium or low>",
    "summary": "A 2-3 sentence summary mentioning specific metrics like the {total_sales} sales, {avg_rating:.1f}/5 rating, {seller_data.get('on_time_rate', 0)*100:.0f}% on-time rate, and {tenure_months} month history"
}}

Respond ONLY with the JSON, no other text.<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{{"""

        return prompt
    
    def generate_credibility_score(self, seller_data):
        """
        Generate credibility score for a seller using Watsonx
        
        Args:
            seller_data: Dictionary containing seller information:
                - seller_id: Unique seller identifier
                - seller_since: Date when seller joined (datetime or ISO string)
                - total_sales: Number of completed sales
                - average_transaction_value: Average order value
                - reviews: List of review dictionaries with 'rating' and 'comment'
                - dispute_rate: Percentage of disputes (0-1)
                - on_time_rate: On-time delivery rate (0-1)
                - avg_response_hours: Average response time
                - verified: Boolean for identity verification
        
        Returns:
            Dictionary with credibility score and analysis
        """
        
        # Build prompt
        prompt = self._build_prompt(seller_data)
        
        try:
            # Generate response from Watsonx
            response = self.model.generate_text(prompt=prompt)
            
            # Parse JSON response
            # Clean response if it contains markdown code blocks or extra text
            response_clean = response.strip()
            
            # Remove markdown code blocks
            if '```json' in response_clean:
                response_clean = response_clean.split('```json')[1].split('```')[0]
            elif '```' in response_clean:
                response_clean = response_clean.split('```')[1].split('```')[0]
            
            # Find JSON object
            start_idx = response_clean.find('{')
            end_idx = response_clean.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                response_clean = response_clean[start_idx:end_idx+1]
            
            response_clean = response_clean.strip()
            
            # Try to parse
            result = json.loads(response_clean)
            
            # Validate that we have actual insights, not generic ones
            if result.get('key_concerns') and len(result['key_concerns']) > 0:
                if all('limited data' in str(c).lower() for c in result['key_concerns']):
                    # AI gave generic response, enhance it with specific metrics
                    result = self._enhance_with_metrics(result, seller_data)
            
            # Add metadata
            result['seller_id'] = seller_data.get('seller_id')
            result['generated_at'] = datetime.now().isoformat()
            result['model_used'] = 'llama-3-3-70b-instruct'
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"Error parsing Watsonx response: {e}")
            print(f"Raw response: {response[:500]}...")
            
            # Fallback: return a metric-based score
            return self._generate_metric_based_score(seller_data)
            
            # Fallback: return a basic score
            return {
                'seller_id': seller_data.get('seller_id'),
                'credibility_score': 50,
                'risk_level': 'medium',
                'recommendation': 'review',
                'confidence': 'low',
                'summary': 'Unable to generate full analysis. Manual review recommended.',
                'error': str(e),
                'raw_response': response
            }
        
        except Exception as e:
            print(f"Error calling Watsonx: {e}")
            raise
    
    def batch_score_sellers(self, sellers_list):
        """
        Score multiple sellers
        
        Args:
            sellers_list: List of seller data dictionaries
            
        Returns:
            List of credibility results
        """
        results = []
        
        for seller in sellers_list:
            try:
                score = self.generate_credibility_score(seller)
                results.append(score)
            except Exception as e:
                print(f"Error scoring seller {seller.get('seller_id')}: {e}")
                results.append({
                    'seller_id': seller.get('seller_id'),
                    'error': str(e),
                    'credibility_score': None
                })
        
        return results
    
    def get_stamp_approval(self, credibility_score):
        """
        Convert credibility score to stamp approval status
        
        Args:
            credibility_score: Score from 0-100
            
        Returns:
            Dictionary with stamp information
        """
        if credibility_score >= 86:
            return {
                'stamp': 'VERIFIED_EXCELLENT',
                'color': 'green',
                'badge': '✓✓✓',
                'message': 'Highly Trusted Seller'
            }
        elif credibility_score >= 61:
            return {
                'stamp': 'APPROVED',
                'color': 'blue',
                'badge': '✓✓',
                'message': 'Reliable Seller'
            }
        elif credibility_score >= 31:
            return {
                'stamp': 'CAUTION',
                'color': 'yellow',
                'badge': '⚠',
                'message': 'Proceed with Caution'
            }
        else:
            return {
                'stamp': 'HIGH_RISK',
                'color': 'red',
                'badge': '✗',
                'message': 'Not Recommended'
            }


# Example usage and testing
if __name__ == "__main__":
    # Initialize scorer
    scorer = WatsonxCredibilityScorer()
    
    # Example seller data
    seller_example = {
        'seller_id': 'SELL_12345',
        'seller_since': '2023-01-15T00:00:00Z',
        'total_sales': 487,
        'average_transaction_value': 1250.50,
        'reviews': [
            {'rating': 5, 'comment': 'Excellent service, fast shipping!'},
            {'rating': 5, 'comment': 'Great quality products, will buy again'},
            {'rating': 4, 'comment': 'Good seller, slight delay in shipping'},
            {'rating': 5, 'comment': 'Professional and responsive'},
            {'rating': 4, 'comment': 'Product as described, packaging could be better'}
        ],
        'dispute_rate': 0.02,
        'on_time_rate': 0.94,
        'avg_response_hours': 3.5,
        'verified': True
    }
    
    # Generate credibility score
    print("Analyzing seller credibility with Watsonx AI...\n")
    result = scorer.generate_credibility_score(seller_example)
    
    # Display results
    print("=" * 60)
    print(f"SELLER CREDIBILITY REPORT")
    print("=" * 60)
    print(f"Seller ID: {result['seller_id']}")
    print(f"Credibility Score: {result['credibility_score']}/100")
    print(f"Risk Level: {result['risk_level'].upper()}")
    print(f"Recommendation: {result['recommendation'].upper()}")
    print(f"Confidence: {result['confidence'].upper()}")
    print(f"\nSummary: {result['summary']}")
    
    print(f"\nKey Strengths:")
    for strength in result.get('key_strengths', []):
        print(f"  ✓ {strength}")
    
    print(f"\nKey Concerns:")
    for concern in result.get('key_concerns', []):
        print(f"  ⚠ {concern}")
    
    # Get stamp approval
    stamp = scorer.get_stamp_approval(result['credibility_score'])
    print(f"\n{stamp['badge']} STAMP: {stamp['stamp']} - {stamp['message']}")
    print("=" * 60)