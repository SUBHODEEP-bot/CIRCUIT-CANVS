## CircuitForge Lab

This is a Vite + React + TypeScript project for visual circuit design.

### Running the frontend only

```sh
cd circuit-canvas
npm install
npm run dev
```

### Building the frontend

```sh
cd circuit-canvas
npm run build
```

The production build will be generated in the `dist` folder.

### Python backend

The project also includes a `app.py` Flask backend (in the parent folder) that can serve the built frontend and proxy API calls to Supabase. After building the frontend, you can run:

```sh
python app.py
```

This will start the full website on `http://localhost:5000`.
