# file upload stack

This package contains:
- frontend static pages: `login.html`, `signup.html`, `upload.html`
- `frontend/nginx.conf` to serve the pages and reverse proxy API calls
- `auth/auth_service.py` for signup/login with JWT and MongoDB
- `backend/app.py` for protected file upload/list/download to Azure Blob Storage
- `docker-compose.yml` to start frontend, auth, backend and MongoDB

## Run
1. Copy `.env.example` to `.env` and change values.
2. Build and start:
   ```bash
   docker compose up --build -d
   ```
3. Open `http://<your-url>/`

## Required Azure configuration
- The VM must be able to reach the Azure Storage Account privately.
- Blob private endpoint and private DNS must already be configured in your Azure network.
- The VM identity used by Docker must have Blob data permissions on the storage account/container.

## Notes
- Login page is the first page.
- Signup is a separate page.
- Upload/list/download page is shown only after successful login because the browser stores the JWT token and sends it as a `Bearer` token to protected routes.


## ✅ ✅ Application Workflow & Architecture Diagram

## Overview
This document describes the full workflow of the JWT-based secure file upload system.

---

## 1. User Access Flow

1. User opens application URL
2. Request goes to NGINX (frontend gateway)
3. NGINX serves login page

---

## 2. Authentication Flow (Login)

Browser → NGINX → Auth Service → MongoDB

- User submits username/password
- Auth service validates credentials
- If valid: JWT token is generated
- Token returned to browser
- Token stored in localStorage

---

## 3. JWT Usage

- JWT is included as:

Authorization: Bearer <token>

- Used in all protected API calls

---

## 4. Upload Flow (Protected)

Browser (JWT) → NGINX → Backend API → Azure Blob Storage

- Token validated in backend
- File uploaded to Blob Storage via private endpoint

---

## 5. List Files Flow

Browser (JWT) → Backend API → Blob Storage → Response

---

## 6. Download Flow

Browser (JWT) → Backend API → Blob → Stream → Browser

---

## 7. Logout Flow

- JWT removed from browser
- User redirected to login page

---

## Architecture Diagram

                +------------------------+
                |        Browser         |
                |   (Login / Upload)     |
                +-----------+------------+
                            |
                            v
                +------------------------+
                |         NGINX          |
                | (Frontend + Routing)   |
                +------+---------+-------+
                       |         |
                       v         v
             +-------------+   +-------------+
             | Auth Service|   | Backend API |
             |  (Flask)    |   |  (Flask)    |
             +------+------+
                    |            |
                    v            v
             +-------------+   +------------------------+
             |  MongoDB    |   | Azure Blob Storage     |
             | (Users DB)  |   | (Private Endpoint)     |
             +-------------+   +------------------------+

---

## Key Concepts

- NGINX acts as reverse proxy
- JWT provides stateless authentication
- MongoDB stores user credentials securely (bcrypt hashed)
- Azure Blob Storage is accessed privately

---

## Summary

Flow:
Login → JWT → Protected APIs → File Upload/Download

This architecture ensures:
- Security
- Scalability
- Clean separation of services



---------
helm deployment:
helm install file-upload-stack-stage oci://registry-1.docker.io/twinkal1710/file-upload-stack --version 1.0.0
helm install istio-ingressgateway istio/gateway -n istio-ingress

