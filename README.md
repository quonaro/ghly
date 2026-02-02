# GHLy

Proxy for GitHub raw content with caching and optional restriction to specific repositories.

## Quick Start with Docker Compose

This is the recommended way to run the application.

### Prerequisites

- Docker
- Docker Compose

### Running the Application

1. **Configure Environment Variables**

   Create a `.env` file from the example:

   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` if necessary (e.g., to restrict allowed repositories or change the cache TTL). By default, it works out of the box with `0.0.0.0` as the host.

2. **Start Services**

   Build and start the containers in detached mode:

   ```bash
   docker-compose up -d --build
   ```

   This will start:
   - **Redis** on port `6374` (mapped from container port 6379)
   - **GHLy App** on port `8000`

3. **Verify Deployment**

   Check if the containers are running:

   ```bash
   docker-compose ps
   ```

   Check the logs if needed:

   ```bash
   docker-compose logs -f
   ```

### Usage

Once running, the service is available at `http://localhost:8000`.

#### Basic Request Format

The standard format is: `/{owner}/{repo}/{path}`. 
By default, it fetches from the `main` branch.

**Example:**
```
http://localhost:8000/quonaro/Nest/README.md
```

#### Specifying Branch/Ref

Use the `ref` query parameter to specify a branch, tag, or commit hash.

**Example:**
```
http://localhost:8000/quonaro/Nest/README.md?ref=v1.0.2
```

#### Forcing Cache Invalidation

To bypass the cache and fetch a fresh version of the file from GitHub, use the `refresh=true` query parameter.

**Example:**
```
http://localhost:8000/quonaro/Nest/README.md?refresh=true
```

#### Complex Paths

The path can include multiple subdirectories.

**Example:**
```
http://localhost:8000/quonaro/Nest/docs/usage/advanced.md?ref=develop&refresh=true
```

## Development

To stop the services:

```bash
docker-compose down
```

To stop and remove volumes (clears Redis data):

```bash
docker-compose down -v
```

## Using Pre-built Image (GHCR)

If you prefer to use the pre-built image from GitHub Container Registry instead of building locally:

1.  **Configure `.env`** as described above.

2.  **Start Services**:

    ```bash
    docker-compose -f compose.ghcr.yml up -d
    ```
