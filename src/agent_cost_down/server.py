"""Single-worker hosted entry point. Secrets arrive only through the runtime environment."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "agent_cost_down.api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )
