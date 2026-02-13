# Documentation Access

The Sible documentation suite is built using Vitepress for high-performance delivery. Use the following instructions to build, host, and access the technical reference.

## Development Environment
To run the documentation locally for live editing:
1.  Ensure Node.js 18+ is installed.
2.  Navigate to the project root.
3.  Install dependencies: `npm install`.
4.  Launch the dev server: `npm run docs:dev`.
5.  Access via: `http://localhost:5173`.

## Production Build
Generate a static optimized version of the documentation:
1.  Execute: `npm run docs:build`.
2.  The output will be located in `docs/.vitepress/dist`.

## Hosting Strategy
The `dist` directory is compatible with any static site host (e.g., GitHub Pages, Vercel, or Nginx).

### Nginx Example Configuration
```nginx
server {
    listen 80;
    server_name docs.sible.local;
    root /path/to/sible/docs/.vitepress/dist;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

## Versioning
Documentation is version-locked to the Sible release. Current Documentation Version: **v1.0.0**.
