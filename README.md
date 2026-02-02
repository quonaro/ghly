# 🚀 GHLy: High-Performance GitHub Proxy

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Litestar](https://img.shields.io/badge/Framework-Litestar-8000FF.svg)](https://litestar.dev/)
[![Redis](https://img.shields.io/badge/Cache-Redis-red.svg)](https://redis.io/)

A blazing-fast proxy for GitHub raw content with advanced caching, repository whitelisting, and dynamic cache control.

---

## ✨ Features

- ⚡ **High-Speed Proxying**: Built on Litestar for asynchronous processing.
- 📁 **Adaptive Caching**: supports both **Redis** (production-grade) and **SQLite** (lightweight/local).
- 🛡️ **Access Control**: Built-in whitelist system to restrict access to specific repositories or organizations.
- 🔄 **Dynamic Refresh**: Force cache invalidation via simple query parameters.
- 🐳 **Docker Ready**: Production-optimized Docker and Compose configurations.

---

## 🛠 Quick Start

### 1. Configure
```bash
cp .env.example .env
```
Edit `.env` to set your preferences (allowed repositories, TTL, etc.).

### 2. Launch
```bash
docker-compose up -d --build
```
This starts **GHLy** (port 8000) and **Redis** (port 6374).

---

## 📖 Usage Guide

The service is available at `http://localhost:8000`.

### URL Format
`/{owner}/{repo}/{path}`

### Query Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ref` | `string` | `main` | Branch, tag, or commit hash. |
| `refresh` | `boolean`| `false`| If `true`, bypasses cache and fetches fresh content from GitHub. |

### Examples

| Action | URL |
| :--- | :--- |
| **Basic** | `http://localhost:8000/quonaro/Nest/README.md` |
| **Specific Version** | `http://localhost:8000/quonaro/Nest/README.md?ref=v1.0.2` |
| **Force Update** | `http://localhost:8000/quonaro/Nest/README.md?refresh=true` |
| **Deep Path** | `http://localhost:8000/owner/repo/src/utils/logger.py?ref=develop` |

---

## ⚙️ Configuration

Control aspects of GHLy via environment variables:

- `REPOSITORIES`: Comma-separated list of allowed `owner/repo` or organizations. Use empty for unrestricted access.
- `CACHE_TTL_SECONDS`: How long to keep files in cache (default: 3600s).
- `USE_REDIS`: Automatic discovery when `REDIS_URL` or `REDIS_HOST` is set.

---

## 🧪 Development

| Command | Description |
| :--- | :--- |
| `docker-compose down` | Stop services |
| `docker-compose down -v` | Stop services and **clear cache** |
| `uv run app/main.py` | Run locally without Docker |

---

## 📦 Using Pre-built Images

Get up and running instantly with images from GHCR:

```bash
docker-compose -f compose.ghcr.yml up -d
```

---

<div align="center">
  <sub>Built with ❤️ for the open-source community</sub>
</div>
