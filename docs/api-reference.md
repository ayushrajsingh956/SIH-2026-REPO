# LegalMetro Shield — API Reference (v1)

Base URL: `/api/v1`  
Specification: OpenAPI 3.1.0  
Authentication: HTTP Bearer JWT in `Authorization` header (`Authorization: Bearer <token>`)  
Error Format: RFC 7807 Problem Details (`application/problem+json`)

---

## 1. Authentication Endpoints (`/api/v1/auth`)

### `POST /api/v1/auth/register`
- **Description**: Registers a new user account. Public registrations default to inactive `viewer` role awaiting administrator approval. Admin caller can provision arbitrary active roles (`admin`, `inspector`, `viewer`).
- **Rate Limit**: 10 requests / minute
- **Request Body**:
  ```json
  {
    "name": "Inspector A. Sharma",
    "email": "sharma.lm@nic.in",
    "password": "SecurePassword123!",
    "district": "North Delhi",
    "state": "Delhi",
    "role": "viewer"
  }
  ```
- **Responses**:
  - `201 Created`: Returns created `UserResponse` object.
  - `409 Conflict`: Email address already registered.

### `POST /api/v1/auth/login`
- **Description**: Authenticates user via email and password, issuing an access token and a refresh token.
- **Rate Limit**: 5 requests / minute
- **Request Body**:
  ```json
  {
    "email": "inspector@legalmetro.gov.in",
    "password": "InspectorPass123!"
  }
  ```
- **Responses**:
  - `200 OK`:
    ```json
    {
      "access_token": "eyJhbGciOi...",
      "refresh_token": "c7f4e9...",
      "expires_in": 1800,
      "user": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "name": "Inspector Sharma",
        "email": "inspector@legalmetro.gov.in",
        "role": "inspector",
        "is_active": true
      }
    }
    ```
  - `401 Unauthorized`: Invalid credentials.
  - `403 Forbidden`: Account pending admin approval.

### `POST /api/v1/auth/refresh`
- **Description**: Rotates the refresh token and issues a new access token. Employs automatic family revocation upon replay detection.
- **Rate Limit**: 10 requests / minute
- **Request Body**: `{"refresh_token": "..."}`
- **Responses**: `200 OK` (new token pair) | `401 Unauthorized`

### `POST /api/v1/auth/logout`
- **Description**: Revokes the refresh token server-side and logs out the session.

---

## 2. Packaging Scans Endpoints (`/api/v1/scans`)

### `POST /api/v1/scans`
- **Description**: Upload packaged commodity photos (1 to 6 images) and enqueue an asynchronous compliance inspection scan.
- **Role Required**: `admin` or `inspector`
- **Rate Limit**: 30 requests / minute
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `images`: List of image files (JPEG, PNG, WebP, max 10MB each).
  - `mode`: `retail` | `wholesale` | `imported` | `ecommerce` (default: `retail`).
  - `font_check_mode`: `relative` | `calibrated` (default: `relative`).
  - `surface_area_cm2`: Optional float for Principal Display Panel (PDP) area.
- **Responses**:
  - `202 Accepted`:
    ```json
    {
      "id": "a850fa97-3f30-4e89-b7b5-2dbd118eb3d1",
      "status": "queued",
      "message": "Scan uploaded successfully and queued for compliance processing.",
      "estimated_processing_seconds": 5
    }
    ```

### `GET /api/v1/scans`
- **Description**: Paginated list of packaging inspection scans.
- **Query Parameters**:
  - `limit`: Integer (default 20, max 100).
  - `offset`: Integer (default 0).
  - `status`: Filter by status (`queued`, `processing`, `completed`, `needs_review`, `failed`).
  - `verdict`: Filter by verdict (`compliant`, `non_compliant`, `needs_review`).
  - `mode`: Filter by inspection mode.
- **Responses**: `200 OK` (`items`, `total`).

### `GET /api/v1/scans/{id}`
- **Description**: Retrieve complete scan details including extracted Rule 6(1) fields, bounding boxes, evaluated statutory violations, and 5-minute presigned image URLs.
- **Responses**: `200 OK` (`ScanDetailResponse`) | `404 Not Found`

### `PATCH /api/v1/scans/{id}/extraction`
- **Description**: Inspector edits OCR/vision extracted values and re-evaluates all compliance rules deterministically.
- **Role Required**: `admin` or `inspector`
- **Responses**: `200 OK` (updated scan with recalculated score and verdict).

### `POST /api/v1/scans/{id}/revalidate`
- **Description**: Re-runs the deterministic rules engine against current extraction data with active rule configurations.

---

## 3. Real-Time Pipeline WebSocket (`/ws/scans/{id}`)

- **URL**: `ws://localhost:8000/ws/scans/{scan_id}`
- **Query Parameter**: `?token=<access_token>`
- **Messages Received**:
  ```json
  {"scan_id": "...", "status": "processing", "stage": "preprocessing"}
  {"scan_id": "...", "status": "processing", "stage": "extracting"}
  {"scan_id": "...", "status": "processing", "stage": "rules_evaluation"}
  {"scan_id": "...", "status": "completed", "verdict": "non_compliant", "score": 45.0}
  ```

---

## 4. Statutory Violations & Overrides (`/api/v1/violations`)

### `GET /api/v1/violations`
- **Description**: Paginated list of statutory violations across all scans with multi-field filtering.
- **Query Parameters**: `severity`, `rule_code`, `status`, `overridden`, `search`, `limit`, `offset`.

### `PATCH /api/v1/violations/{id}/override`
- **Description**: Inspector manually overrides or waives a detected statutory violation (e.g. statutory exemption under Rule 26) with mandatory written legal rationale ($\ge 10$ characters).
- **Role Required**: `admin` or `inspector`
- **Request Body**:
  ```json
  {
    "overridden": true,
    "override_reason": "Exemption granted under Rule 26 for small packages under 10g."
  }
  ```

---

## 5. Inspection Reports (`/api/v1/reports`)

### `POST /api/v1/reports`
- **Description**: Generates official PDF and DOCX inspection notices with base64 evidence images and statutory citations, uploads to MinIO, and creates a Report record.
- **Role Required**: `admin` or `inspector`
- **Request Body**: `{"scan_id": "uuid"}`
- **Responses**: `201 Created` (`ReportResponse`)

### `GET /api/v1/reports`
- **Description**: Paginated list of generated official reports.

### `GET /api/v1/reports/{id}/download`
- **Description**: Generates a secure, 5-minute (300s) presigned URL to download the report from MinIO.
- **Query Parameter**: `format=pdf` or `format=docx`
- **Responses**:
  ```json
  {
    "report_id": "uuid",
    "format": "pdf",
    "download_url": "https://storage.legalmetro.gov.in/legalmetro-scans/reports/...X-Amz-Signature=...",
    "expires_in_seconds": 300
  }
  ```

---

## 6. Admin Endpoints (`/api/v1/admin`)

### `GET /api/v1/admin/users`
- **Description**: Paginated management list of system users. (Admin only)

### `PATCH /api/v1/admin/users/{id}`
- **Description**: Mutate user role (`admin`, `inspector`, `viewer`) or active status. (Admin only)

### `GET /api/v1/admin/audit-logs`
- **Description**: Filterable security and audit log viewer recording all user mutations, overrides, logins, and scans. (Admin only)

### `GET /api/v1/admin/rules`
- **Description**: View all registered compliance rules with active status and severity levels.

### `PATCH /api/v1/admin/rules/{code}`
- **Description**: Override rule severity (`critical`, `major`, `minor`) or toggle rule activation. (Admin only)

---

## 7. Analytics & Dashboard (`/api/v1/analytics`)

### `GET /api/v1/analytics/dashboard`
- **Description**: Summary metrics including total scans, compliance rate, top 5 violated LMPC rules, and district-wise enforcement breakdown.

### `GET /api/v1/analytics/trends`
- **Description**: Chronological compliance rates and violation frequencies aggregated by week or month.
