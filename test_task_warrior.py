import json, subprocess
import dotenv
import os

dotenv.load_dotenv()

def tw(*args: str):
    return subprocess.run([os.environ.get("TASK_WARRIOR_PATH")] + list(args), capture_output=True, text=True, check=False)

res = tw("add", "cloud")

print(res.stdout)