# Master Service Agreement (MSA) & End-User License Agreement (EULA)
**Provided by Associative**

---

## 1. GRANT OF LICENSE
Subject to the terms and conditions of this Agreement, Associative hereby grants to the Client a **Single-Entity, Non-Transferable, Non-Sublicensable Lifetime License for Internal Business Operations**. 

Under no circumstances does this license grant the Client the right to resell, redistribute, white-label, or otherwise commercialize the underlying Software, its source code, or its compiled binaries to any third party. The software must strictly be used to automate and facilitate the Client’s own internal business operations.

## 2. INTELLECTUAL PROPERTY RIGHTS
All rights, title, and interest in and to the Software, including but not limited to the Artificial Intelligence workflows, multi-modal processing pipelines, proprietary algorithms, and infrastructure-as-code scripts, remain the exclusive property of Associative. Delivery of compiled binaries or containerized deployments does not constitute a transfer of ownership.

## 3. TECHNICAL PROTECTIONS & UNAUTHORIZED TAMPERING
The Software is delivered via compiled C-extensions (Cython) and strictly controlled Docker containers. It includes a cryptographic license key validation system bound to the Client's registered Host Domain/IP and Hardware ID. 

**Prohibited Actions:** The Client shall not, nor permit any third party to:
1. Reverse engineer, decompile, disassemble, or otherwise attempt to derive the source code of the Software.
2. Circumvent, modify, disable, or tamper with the `license.py` validation system or Associative License Server communication.
3. Extract core AI processing layers or backend components for use outside of the licensed application.
4. Distribute or share the provided Docker containers or `.pyd`/`.so` binary files outside of the authorized deployment environment.

## 4. SEVERE FINANCIAL PENALTIES
Any breach of Section 3 (Prohibited Actions), unauthorized redistribution, or resale of the Software by the Client or its employees will result in immediate and irreversible termination of this License. 

Furthermore, the Client agrees to be held liable for severe financial penalties. Unauthorized distribution or reverse engineering shall incur liquidated damages of no less than **[Insert High Penalty Amount, e.g., $500,000 USD or equivalent]** per violation, in addition to Associative’s right to pursue injunctive relief and actual damages for lost revenue and intellectual property theft.

## 5. HOSTING & DEPLOYMENT 
If the Software is deployed on-premise, it must be deployed using the authorized Infrastructure-as-Code definitions provided by Associative. The Software will periodically ping the Associative-controlled licensing server for authorization tokens. Revocation of this token by Associative (e.g., for breach of contract) will result in the immediate cessation of Software functionality.

---
*Disclaimer: This is a draft template provided for structural purposes. Associative should have this document reviewed and finalized by a qualified legal professional before presenting it to clients.*
