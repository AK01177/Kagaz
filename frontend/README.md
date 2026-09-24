# Kagaz Frontend

Frontend application for Kagaz, built with Next.js, React, TypeScript, and Tailwind CSS.

## Prerequisites

- Node.js 24+
- npm

## Setup

From the repository root:

```bash
cd frontend
npm install
```

## Environment Variables

Create a local environment file from the provided example:

```bash
cp .env.example .env.local
```

Add the required environment variables to `.env.local` when they are defined for the project.

Do not commit `.env.local` or any file containing secrets.

## Development

Start the development server:

```bash
npm run dev
```

The application will be available at:

http://localhost:3000

## Application Routes

The initial frontend route structure is:

| Route | Purpose |
|---|---|
| `/` | Application landing page |
| `/login` | User authentication |
| `/dashboard` | Main user dashboard |
| `/documents` | Document management |
| `/documents/[id]` | Individual document details |
| `/review` | Document review queue |
| `/approvals` | Document approval queue |
| `/admin/users` | User, role, and permission management |

The application uses the Next.js App Router.

The `/documents/[id]` route is a dynamic route used to access an individual document by its ID.

## Project Structure

```text
frontend/
├── app/
│   ├── login/
│   │   └── page.tsx
│   ├── dashboard/
│   │   └── page.tsx
│   ├── documents/
│   │   ├── [id]/
│   │   │   └── page.tsx
│   │   └── page.tsx
│   ├── review/
│   │   └── page.tsx
│   ├── approvals/
│   │   └── page.tsx
│   ├── admin/
│   │   └── users/
│   │       └── page.tsx
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
├── public/
├── .env.example
├── package.json
├── package-lock.json
├── next.config.ts
├── postcss.config.mjs
├── eslint.config.mjs
└── tsconfig.json
```

## Lint

Run ESLint to check the frontend code:

```bash
npm run lint
```

## Production Build

Create an optimized production build:

```bash
npm run build
```

A successful production build confirms that the frontend compiles correctly and that the configured application routes are valid.

## Production Server

After creating a production build, start the production server:

```bash
npm run start
```

The frontend will be available at:

http://localhost:3000

## Verification

Before committing frontend changes, run:

```bash
npm run lint
npm run build
```

Both commands should complete successfully without errors.

## Technology Stack

- Next.js
- React
- TypeScript
- Tailwind CSS
- ESLint
