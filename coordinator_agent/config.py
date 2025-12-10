import os

from dotenv import load_dotenv
load_dotenv()

LLM_MODEL_ID = os.getenv('LLM_MODEL_ID')

UCHINA_GUCHI_AGENT_URL = os.getenv('UCHINA_GUCHI_AGENT_URL')

# 必要に応じて他のエージェントのURLもここに追加
# ****_AGENT_URL = os.getenv('****_AGENT_URL')