from supabase import create_client
import os
from dotenv import load_dotenv

# project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# env_path = os.path.join(project_root, '.env')
load_dotenv()

url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # or anon key for public use
supabase = create_client(url, key)
