import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The core (civic-engagement). Pinned to a commit, it's the copy npm installed
// in node_modules. A local checkout (`scripts/core.py local`) is served from
// its own sources instead, so that its edits reload live (npm's copy only
// changes with the next `scripts/core.py local`), with the libraries it shares
// with the app (three.js, React, ...) taken from the app's node_modules, once.
const here = fileURLToPath(new URL('.', import.meta.url))
const readJson = (file: string) => JSON.parse(readFileSync(file, 'utf8'))
const coreSpec: string = readJson(path.join(here, 'package.json')).dependencies['civic-engagement']
const localCore = coreSpec.startsWith('file:') ? path.resolve(here, coreSpec.slice('file:'.length)) : null
const core = localCore ?? path.join(here, 'node_modules/civic-engagement')
const coreLibraries = Object.keys(readJson(path.join(core, 'package.json')).dependencies)
  .filter((name) => !name.startsWith('@types/'))
const resolve = localCore
  ? {
      alias: [{ find: /^civic-engagement$/, replacement: path.join(localCore, 'frontend/src/index.ts') }],
      dedupe: coreLibraries,
    }
  : undefined
const fs = localCore ? { allow: [here, localCore] } : undefined

// The backend, for both the dev server and the production preview: on
// :8000 unless CIVIC_ENGAGEMENT_BACKEND says otherwise (see the README).
const proxy = {
  '/api': process.env.CIVIC_ENGAGEMENT_BACKEND ?? 'http://localhost:8000',
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve,
  // The core's static files (3D models, textures).
  publicDir: path.join(core, 'frontend/public'),
  server: { proxy, fs },
  // `npm run preview` serves the production build: what to use for
  // workshops, demos and performance measurements — the development build
  // is several times slower (React's development mode alone adds seconds
  // to a date change in the 3D view, see the README).
  preview: { proxy },
  // maplibre-gl loads its tiling logic in a worker via a relative URL that
  // breaks under Vite's dependency pre-bundling (the worker chunk goes
  // missing, so sources silently never finish loading) — exclude it so Vite
  // serves it as native ESM instead.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
