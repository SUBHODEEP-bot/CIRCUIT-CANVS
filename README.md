# CircuitForge Lab

A professional circuit design and simulation platform built with React, TypeScript, Flask, and Supabase.

## 🎯 Features

- **Visual Circuit Design**: Drag-and-drop module placement and wiring
- **Module Library**: Pre-built components (microcontrollers, sensors, etc.)
- **Real-time Connections**: Create and manage circuit connections visually
- **Professional PDF Export**: Export circuit diagrams as A4 PDFs with designer credits
- **User Accounts**: Secure authentication with Supabase
- **Admin Panel**: Manage modules and components
- **Responsive Design**: Works on desktop browsers

## 🚀 Quick Start

### Prerequisites
- Node.js 16+
- Python 3.8+
- Supabase account (free tier works)

### Local Development

1. **Clone and setup**
```bash
git clone <repository>
cd circuit-lab
```

2. **Backend setup**
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Supabase credentials
```

3. **Frontend setup**
```bash
cd circuit-canvas
npm install
cp .env.example .env
# Edit .env with same Supabase credentials
```

4. **Build frontend**
```bash
npm run build
cd ..
```

5. **Run the app**
```bash
python app.py
```

Visit `http://localhost:5000`

## 📦 Project Structure

```
circuit-lab/
├── app.py                 # Flask backend
├── requirements.txt       # Python dependencies
├── circuit-canvas/        # React frontend
│   ├── src/
│   │   ├── pages/        # Page components
│   │   ├── components/   # React components
│   │   ├── lib/          # Utilities and API
│   │   └── hooks/        # React hooks
│   ├── package.json      # Node dependencies
│   └── dist/             # Built frontend (generated)
├── DEPLOYMENT.md         # Render deployment guide
└── .env.example          # Environment template
```

## 🔐 Environment Variables

### Backend (.env)
```env
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc...
ADMIN_NAME=admin
ADMIN_PASSWORD=yourpassword
```

### Frontend (circuit-canvas/.env)
```env
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=eyJhbGc...
```

## 🌐 Deployment

### Deploy to Render

See [DEPLOYMENT.md](./DEPLOYMENT.md) for complete instructions.

Quick summary:
1. Push to GitHub
2. Create new web service on Render
3. Set environment variables
4. Deploy!

## 📊 Database Setup

CircuitForge requires these tables in Supabase:

- `auth.users` - Authentication (built-in)
- `profiles` - User profiles
- `projects` - User circuit projects
- `modules` - Component definitions
- `module_pins` - Pin definitions for modules

See Supabase migrations in `circuit-canvas/supabase/migrations/` for full schema.

## 🛠️ Tech Stack

**Frontend:**
- React 18
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui components
- html2canvas & jsPDF (for PDF export)

**Backend:**
- Flask (Python)
- Supabase (Auth & Database)

## 📝 API Endpoints

### Authentication
- `POST /api/auth/signup` - Create account
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/session` - Get current session
- `PUT /api/auth/profile` - Update display name

### Projects
- `GET /api/projects` - List user's projects
- `POST /api/projects` - Create new project
- `GET /api/projects/<id>` - Get project details
- `PUT /api/projects/<id>` - Update project
- `DELETE /api/projects/<id>` - Delete project

### Modules
- `GET /api/modules` - List all modules
- `GET /api/module-pins` - List pins for a module

### Admin
- `POST /api/admin/login` - Admin authentication
- `POST /api/admin/modules` - Create module
- `PUT /api/admin/modules/<id>` - Update module
- `DELETE /api/admin/modules/<id>` - Delete module

## 🧪 Testing

```bash
# Frontend tests
cd circuit-canvas
npm run test

# Lint frontend
npm run lint
```

## 📋 Features in Detail

### Circuit Design
- Add modules from library to canvas
- Drag modules to reposition
- Click pins to create connections
- Add waypoints to wires for custom routing
- Change wire colors
- Delete wires with Delete key

### PDF Export
- Export circuit as professional A4 PDF
- Includes project name and designer credits
- Shows all components used
- Landscape layout for better visibility
- High-quality 4x resolution

### Admin Panel
- Upload custom modules with images
- Define module pins (positions and names)
- Manage the component library

## 🐛 Troubleshooting

**Frontend won't build?**
```bash
cd circuit-canvas
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Supabase connection fails?**
- Check VITE_SUPABASE_URL is correct
- Check API key has anon permissions
- Verify RLS policies allow operations

**PDF export not working?**
- Check browser console for errors
- Ensure canvas has content
- Try with simpler circuit first

## 📄 License

MIT

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

Made with ❤️ by Subhodeep For updates and support, visit the project repository.
