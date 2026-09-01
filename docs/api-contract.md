# API Contract

> Owned by Person 6 (Research / Tech Lead)

## Base URL

TBD — owned by Person 6

```
https://<host>:<port>/api/v1
```

## Authentication

TBD — owned by Person 6

---

## Endpoints

### 1. Evidence Import

#### `POST /api/v1/evidence/import`

**Description:** TBD — owned by Person 6

**Request:**
```json
{
  "TODO": "define request schema"
}
```

**Response:**
```json
{
  "TODO": "define response schema"
}
```

---

### 2. Recovery Status

#### `GET /api/v1/recovery/status/:sessionId`

**Description:** TBD — owned by Person 6

**Request:** N/A (path parameter)

**Response:**
```json
{
  "TODO": "define response schema"
}
```

---

### 3. Recovery Results

#### `GET /api/v1/recovery/results/:sessionId`

**Description:** TBD — owned by Person 6

**Request:** N/A (path parameter)

**Response:**
```json
{
  "TODO": "define response schema"
}
```

---

### 4. Erasure Start

#### `POST /api/v1/erasure/start`

**Description:** TBD — owned by Person 6

**Request:**
```json
{
  "TODO": "define request schema"
}
```

**Response:**
```json
{
  "TODO": "define response schema"
}
```

---

### 5. Erasure Status

#### `GET /api/v1/erasure/status/:jobId`

**Description:** TBD — owned by Person 6

**Request:** N/A (path parameter)

**Response:**
```json
{
  "TODO": "define response schema"
}
```

---

### 6. Erasure Certificate

#### `GET /api/v1/erasure/certificate/:jobId`

**Description:** TBD — owned by Person 6

**Request:** N/A (path parameter)

**Response:**
```json
{
  "TODO": "define response schema"
}
```

---

### 7. Audit Log

#### `GET /api/v1/audit/log`

**Description:** TBD — owned by Person 6

**Query Parameters:**
```
?from=<ISO8601>&to=<ISO8601>&actor=<string>&action=<string>&limit=<int>&offset=<int>
```

**Response:**
```json
{
  "TODO": "define response schema"
}
```
