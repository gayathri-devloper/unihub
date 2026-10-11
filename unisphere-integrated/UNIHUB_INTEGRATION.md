# UniHub integration into UniSphere

The standalone Faculty & Research UniHub portal has been integrated into the UniSphere Team 07 entry point.

## What was preserved
- The original `faculty_portal/frontend` files are copied unchanged to `public/unihub/`.
- The original Flask + SQLite backend is bundled under `unihub/backend/`.
- Existing UniSphere navigation, authentication and RBAC still select the `unihub` module.
- The previous Team 07 React placeholder remains in the repository but is no longer rendered by the UniHub entry point.

## Run

### Windows
Run `run-unihub.bat`.

### Linux/macOS
Run `./run-unihub.sh`.

These launch the UniHub API backend and UniSphere/Vite frontend, then open the frontend in your browser. Vite selects and prints its actual **Local** URL (normally `http://localhost:5173`; it may choose another port if that one is already in use).

Use the Vite **Local** URL for UniSphere. Do not open the Flask backend port for the integrated experience: its root route serves the standalone UniHub faculty directory. In UniSphere, sign in with a role that has UniHub access and select **UniHub**.

The Vite development server finds an available backend port and proxies the original UniHub API calls to that exact backend, while the standalone UniHub pages remain under `/unihub/`.

## Note
The integrated frontend is intentionally kept as the original standalone HTML/CSS/JS portal. This avoids rewriting your UniHub UI into React and preserves its behavior and styling. Production deployment should deploy the Flask backend alongside the UniSphere frontend and configure the same API/static routing.
