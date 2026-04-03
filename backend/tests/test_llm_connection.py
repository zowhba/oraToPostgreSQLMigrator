import sys
import os
import logging

# 프로젝트 루트를 path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.llm_client import convert_query
from backend.utils.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    logger.info(f"Testing LLM Connection...")
    logger.info(f"Model: {Config.AI_DEPLOY_MODEL}")
    logger.info(f"Endpoint: {Config.AI_ENDPOINT}")
    
    test_sql = "<select id='test'>SELECT * FROM DUAL</select>"
    try:
        result = convert_query(test_sql, "schema info context", "select")
        logger.info("Success! LLM Response received.")
        # logger.info(f"Result: {result.get('converted_sql')}")
        return True
    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_connection()
