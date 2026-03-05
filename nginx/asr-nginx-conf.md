# =========================
# Aether ASR - Production
# =========================

upstream asr_api {
    server 127.0.0.1:8010;
    keepalive 32;
}

upstream asr_ui {
    server 127.0.0.1:3010;
    keepalive 32;
}

limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=1r/s;

map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name asr.aetherpro.us;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name asr.aetherpro.us;

    ssl_certificate /etc/letsencrypt/live/asr.aetherpro.us/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/asr.aetherpro.us/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 200M;

    # === API ROUTES ===
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 600;
        proxy_connect_timeout 600;
    }

    # === OpenAI-Compatible API Routes ===
    location /v1/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 600;
        proxy_connect_timeout 600;
        client_max_body_size 200M;
    }

    # === Billing Routes ===
    location /billing/ {
        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # === Upload Endpoint ===
    location /upload/ {
        limit_req zone=upload_limit burst=5 nodelay;

        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # ==========================
    # ADD THESE ROUTES (DOCS)
    # ==========================

    # FastAPI docs (Swagger / ReDoc) — ensure these do NOT hit the UI SPA
    location = /docs {
        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs/ {
        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /redoc {
        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /redoc/ {
        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # OpenAPI schema (docs load this)
    location = /openapi.json {
        proxy_pass http://asr_api;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # === UI ===
    location / {
        proxy_pass http://asr_ui;
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;

        proxy_set_header Host $host;
    }
}

