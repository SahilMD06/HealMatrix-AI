# Vercel deployment

`vercel.json` in this folder configures the frontend as a static Vite build
with client-side routing (every path not under `/assets` falls through to
`index.html`, so React Router's routes resolve on a hard refresh or direct
link, not just client-side navigation).

## Setup

Vercel only reads `vercel.json` from the directory it treats as the project
root, and this repo's frontend lives in `frontend/`, not the repo root. Two
ways to connect it:

1. **Recommended:** import the repo in the Vercel dashboard, set **Root
   Directory** to `frontend`, and copy this file to `frontend/vercel.json`
   (or symlink it) so Vercel picks it up from the directory it actually
   builds.
2. Alternatively, skip `vercel.json` entirely and set the same three values
   (Build Command `npm run build`, Output Directory `dist`, Install Command
   `npm ci`) directly in the dashboard's Framework Settings — Vercel
   auto-detects Vite and gets these right by default, so `vercel.json` here
   mainly documents the SPA rewrite rule a fresh dashboard setup would miss.

## Required environment variable

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | The deployed Render API's public URL plus `/api/v1`, e.g. `https://healmatrix-api.onrender.com/api/v1` |

Set this in the Vercel project's **Environment Variables** for the
Production environment before the first deploy — `frontend/src/services/api.js`
falls back to `/api/v1` (a same-origin relative path) if it is unset, which
is only correct for local dev behind Vite's proxy, not a deployed Vercel
static site talking to a separate Render origin.

## CORS

The API's `BACKEND_CORS_ORIGINS` (see `deployment/render/render.yaml`) must
include this Vercel deployment's exact origin (e.g.
`https://healmatrix.vercel.app`), or every request will be blocked by the
browser regardless of how correctly `VITE_API_BASE_URL` is set.
