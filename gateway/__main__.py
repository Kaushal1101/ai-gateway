import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

port = int(os.getenv("GATEWAY_PORT", "8000"))

uvicorn.run("gateway.main:app", host="0.0.0.0", port=port, reload=True)
