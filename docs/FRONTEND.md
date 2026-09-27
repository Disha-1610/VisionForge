# The Web App

> This describes the operator-facing web app.
> Checked against the code in September 2026.

---

## Table of contents

1. [What the operator does](#1-what-the-operator-does)
2. [Technology and versions](#2-technology-and-versions)
3. [Pages and routes](#3-pages-and-routes)
4. [Components](#4-components)
5. [The look and feel](#5-the-look-and-feel)
6. [Watching an inspection live](#6-watching-an-inspection-live)
7. [Keeping the user logged in](#7-keeping-the-user-logged-in)
8. [Talking to the backend](#8-talking-to-the-backend)
9. [The phone QR code](#9-the-phone-qr-code)
10. [Bundle size](#10-bundle-size)
11. [What the old documentation got wrong](#11-what-the-old-documentation-got-wrong)

---

## 1. What the operator does

The whole flow is designed around one person standing at a receiving dock with a part in their hand.

1. **Log in.** Email and password.
2. **Upload a photo.** Drag it onto the page, use the computer's camera, or open the same page on a
   phone and photograph it there.
3. **Watch it work.** A progress rail fills up as the 8 pipeline stages run.
4. **Read the result.** A banner shows the verdict and the written explanation. Below it, the two
   images sit side by side with boxes over anything that was found.
5. **Decide.** Approve the result, or override it with a note. That note is saved.
6. **Download the PDF** if they need to file it.
7. **Check trends** on the analytics page.

## 2. Technology and versions

**The old documentation said React 18 and Vite 5. Both are wrong.**

| | Installed version |
|---|---|
| React | **19.2.8** |
| React DOM | 19.2.8 |
| Vite | **8.3.0** |
| React Router | 7.18.3 |
| Tailwind CSS | 3.4.19 |
| Node required | **20.19+ or 22.12+** |

**Node 18 does not work.** Vite 8 requires a newer version. The old documentation said Node 18 was
the minimum.

### Everything installed

**Main dependencies:**

| Package | Version | What it does |
|---|---|---|
| axios | 1.20.0 | Talking to the backend |
| react-router-dom | 7.18.3 | Page navigation |
| recharts | 3.10.1 | Charts on the analytics page |
| lucide-react | 1.46.0 | The icon set |
| react-markdown | 10.1.0 | Rendering the judge's written explanation |
| qrcode.react | 4.2.0 | The phone QR code |
| clsx | 2.1.1 | Conditional class names |
| tailwind-merge | 3.7.0 | Merging Tailwind classes safely |

**Development dependencies:**

| Package | Version |
|---|---|
| Vite | 8.3.0 |
| React plugin for Vite | 6.1.1 |
| Tailwind CSS | 3.4.19 |
| PostCSS | 8.5.28 |
| autoprefixer | 10.6.0 |
| oxlint | 1.81.0 |
| TypeScript types | React 19.2.18, React DOM 19.2.7 |

**Scripts:**

| Command | What it does |
|---|---|
| `npm run dev` | Start the development server on port 5173 |
| `npm run build` | Build for production |
| `npm run lint` | Run oxlint |
| `npm run preview` | Preview a production build |
| `npm run tunnel` | Start a public Cloudflare tunnel |

**There is no `test` script and no frontend test suite.** All 204 tests are on the backend. There
are no tests for the React components.

## 3. Pages and routes

Eight routes, defined in `src/App.jsx`.

| Path | Page | Who can see it |
|---|---|---|
| `/` | LandingPage | Anyone |
| `/login` | LoginPage | Anyone |
| `/dashboard` | DashboardPage | Logged in |
| `/inspections/new` | NewInspectionPage | Logged in |
| `/inspections/:id` | InspectionDetailPage | Logged in |
| `/reports` | ReportsPage | Logged in |
| `/analytics` | AnalyticsPage | Logged in |
| anything else | NotFoundPage | Anyone |

**Five of the seven real pages are wrapped in a protected shell.** The `ProtectedRoute` component
checks for a valid token and redirects to the login page if there is not one. Inside that shell sits
a sidebar, a top bar, and the page itself.

**There is no mobile page and no mobile route.** The old documentation described a phone intake
view that uploaded to a desktop queue. That does not exist. When the QR code is scanned, the phone
opens the same inspection page, and the person takes the photo and submits it on the phone like any
other upload. **The two devices are independent browser sessions and nothing synchronises them.**

## 4. Components

Nineteen components, in four folders.

### Shared components — `components/common/`

| File | Lines | What it does |
|---|---|---|
| `Button.jsx` | 52 | A button with a loading spinner built in |
| `EmptyState.jsx` | 27 | Shown when a list has nothing in it |
| `Logo.jsx` | 160 | The logo mark and the wordmark |
| `Modal.jsx` | 48 | A popup dialog |
| `SkeletonLoader.jsx` | 13 | A pulsing placeholder while loading |
| `StatCard.jsx` | 53 | One number on the dashboard, with a label and an icon |
| `StatusChip.jsx` | 50 | A coloured pill showing a status or verdict |

**The old documentation listed five of these seven.** It missed `EmptyState` and `Logo`.

### Inspection components — `components/inspection/`

| File | Lines | What it does |
|---|---|---|
| `CameraModal.jsx` | 154 | Live camera in the browser, returns a photo as a file |
| `DesktopGuardModal.jsx` | 101 | Warns desktop users their photo may be rejected, and shows a QR code for using a phone instead |
| `DualImageCanvas.jsx` | 315 | The two images side by side, with a shared zoom control and boxes over detections |
| `EvidenceCard.jsx` | 315 | One specialist's finding, as a card |
| `MarkdownText.jsx` | 155 | Renders the judge's written explanation, cleaning it up first |
| `PipelineProgress.jsx` | 131 | The 8-stage progress rail |
| `ReviewModal.jsx` | 138 | The approve and override dialog |
| `VerdictBanner.jsx` | 327 | The big result banner at the top of a result |

**The old documentation listed four of these eight.** It missed `DesktopGuardModal`,
`MarkdownText`, `ReviewModal`, and `VerdictBanner` — the last being the most prominent thing on the
result page.

### Layout components — `components/layout/`

| File | Lines | What it does |
|---|---|---|
| `AppLayout.jsx` | 37 | The shell: sidebar, top bar, and the page |
| `Sidebar.jsx` | 123 | Navigation, and the sign-out button |
| `Topbar.jsx` | 62 | Page title, connection status, who is logged in |

### Product components — `components/products/`

| File | Lines | What it does |
|---|---|---|
| `GoldenRepositoryDrawer.jsx` | 234 | A slide-over panel for browsing and uploading reference images |

### State and data

| File | What it does |
|---|---|
| `context/AuthContext.jsx` | Holds the logged-in user, the token, and the role. Exposes login, register, and logout |
| `context/ToastContext.jsx` | Short notifications that appear and disappear |
| `hooks/usePipelineSSE.js` | Opens the live connection and tracks progress |

**The AuthContext exposes:** `user`, `token`, `role`, `isAdmin`, `isOperator`,
`isAuthenticated`, `loading`, `login`, `register`, `logout`.

**The old documentation claimed there was a `useInspectionDetail` hook holding the current case in
context.** There is no such hook. The inspection state is held in the page component, not in a
shared context.

## 5. The look and feel

A dark industrial dashboard, designed to stay readable under bright factory lighting.

### The colours

Defined once in `tailwind.config.js`:

| Name | Hex | Used for |
|---|---|---|
| `bg` | `#070b12` | The page background. Near-black with a blue tint |
| `surface` | `#0d1527` | Panels |
| `card` | `#121e36` | Cards |
| `panel` | `#162340` | Raised panels |
| `border` | `#1f3154` | Dividers and card edges |
| `border-light` | `#2b4474` | Hover states |
| `accent` | `#06b6d4` | Links and highlights |
| `cyan` | `#00f0ff` | The primary highlight colour |
| `emerald` | `#10b981` | Pass, accept, good |
| `crimson` | `#ef4444` | Fail, reject, bad |
| `amber` | `#f59e0b` | Warning, review |
| `muted` | `#94a3b8` | Secondary text |

**These were correct in the old documentation.**

### The fonts

| Use | Font |
|---|---|
| Everything | Outfit, falling back to Inter, then the system font |
| Anything technical, such as case numbers and scores | JetBrains Mono |

**Also correct in the old documentation.**

### Two animations

A slow pulse and a glow effect, both defined in the Tailwind config. The glow is used on the primary
highlight elements.

## 6. Watching an inspection live

This is the custom hook, `usePipelineSSE.js`, and it is the most interesting piece of the front end.

### How it works

When an inspection starts, the hook opens a live connection to the server and listens for messages.
Each message tells it which stage is running and how far along the inspection is. That drives the
progress rail.

**The fallback.** If the live connection drops, the hook starts asking the server for the status
every **2,500 milliseconds** instead. This is in the frontend code, not the server.

**The old documentation said the server sets that interval. It does not.** The server checks its own
record every 500 milliseconds. The 2.5 seconds is entirely the browser's choice.

### What the hook actually listens for

**The old documentation said it listened for `stage_progress`, `evidence_card`, and
`pipeline_complete`.** It does not. **None of those event names exist anywhere in the backend.**

What the hook actually listens for:

| What | How |
|---|---|
| Ordinary progress messages | The default message handler |
| The final result | An event named `verdict` |
| A stream timeout | An event named `error` |

**So the hook is correct and the old documentation was wrong.** The frontend and backend agree with
each other. Only the documentation was out of step.

### What it tracks

`currentStage`, `stageName`, `completedStages`, `status`, `verdict`, `policyAction`, `error`,
`detail`, `isDone`.

**The old documentation showed a single `evidenceCards` array with a reducer that appended each
card as it arrived.** There is no such array and no such reducer. Cards are fetched once at the end,
from the inspection record, not streamed.

### The bug worth knowing about

On the most common path, the final `verdict` message **does not contain the verdict**. The hook reads
`data.verdict` and `data.policyAction`, gets nothing, and the result banner shows a blank verdict.

The fix is a small change on the server. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 4.

## 7. Keeping the user logged in

### Refreshing the token

The API client reads the expiry time out of the access token and schedules a refresh **60 seconds
before it expires.**

**The old documentation said a fixed 29-minute timer.** There is no fixed timer. The client reads
the actual expiry out of the token, which is better, because it survives a server change to the
token lifetime.

### Where the token lives

In the browser's local storage. That is convenient and it has a downside: a script running on the
same origin could read it. For this project's scale that is an accepted trade-off, but it is worth
knowing.

### A real bug

The QR code modal fetches the machine's network address with a bare `fetch`, without the token.
That request fails with 401, so the fallback quietly breaks. See
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 5.

## 8. Talking to the backend

### The base address

Hard-coded as `/api/v1` in `src/services/api.js`.

**`frontend/.env.example` sets `VITE_API_BASE_URL=/api/v1`, but that setting is never read.** It is
declared and unused. Changing it does nothing.

### The development proxy

`vite.config.js` forwards two paths to the backend on port 8000:

| Path | Goes to |
|---|---|
| `/api` | `http://localhost:8000` |
| `/static` | `http://localhost:8000` |

So in development the browser calls `/api/v1/...` on port 5173, and Vite passes it through. No
cross-origin request, so no CORS trouble in development.

### The tunnel

`vite.config.js` allows three tunnel hostnames through, so the dev server works behind a public
tunnel: `.trycloudflare.com`, `.ngrok.app`, and `.loca.lt`.

### The request client

One client handles everything: attaching the token, refreshing it when it is close to expiring, and
retrying once after a refresh if the first attempt came back unauthorised.

## 9. The phone QR code

When a desktop user opens the new inspection page, the app shows a modal explaining that a phone
will take a better photo, and shows a QR code.

**What is actually happening, precisely:**

- The QR code contains **the current page address**, not a special mobile intake route.
- Scanning it opens the same page on the phone.
- The person photographs on the phone and submits it there. **The photo does not appear on the
  desktop.** There is no synchronisation between the two sessions, and nothing polls the desktop for
  a phone upload.
- The camera uses the rear-facing camera where available.

**Four corrections to the old documentation:**

- It said the backend starts the tunnel automatically. **It does not.** A person runs
  `npm run tunnel`, and the tunnel process is a script in the frontend folder.
- It said photos taken on the phone upload "directly to the desktop queue". They do not. The photo
  is a file in the phone's browser, submitted the same way any other upload is.
- It said the photo "appears in the desktop browser". **It does not.** The two devices are separate
  sessions. If the operator wants the result on the desktop, they open the inspection there
  afterwards.
- It said the tunnel exposes only the inspection intake. **It exposes the whole development server**,
  which is every page.

## 10. Bundle size

Measured from the last production build in `frontend/dist`:

| File | Uncompressed | Gzipped |
|---|---|---|
| `index-D2YeOHG0.js` | 976 KB | 284 KB |
| `index-DAP4uHhA.css` | 48 KB | 9 KB |
| `index.html` | 0.8 KB | — |
| `icons.svg` | 4.9 KB | — |

**One JavaScript file, 284 KB gzipped.** The old documentation claimed "under 350 KB gzipped" with
code splitting and lazy loading. The total happens to be in that range, but the mechanism is not
there.

**There is no code splitting.** There is no `React.lazy` anywhere in the project, and no dynamic
import. Everything loads in one file, in one request.

The obvious split points, if it were worth doing, are the routes. The analytics page pulls in Recharts,
which is most of the weight, and nobody on the receiving dock needs it.

## 11. What the old documentation got wrong

| Claim | Reality |
|---|---|
| React 18.3 | **React 19.2.8** |
| Vite 5.4 | **Vite 8.3.0** |
| Node 18 minimum | **Node 20.19+ or 22.12+** |
| A fixed 29-minute token timer | Reads the real expiry, refreshes 60 seconds early |
| Listens for `stage_progress` | Listens for the default message handler |
| Listens for `evidence_card` | No such event exists |
| Listens for `pipeline_complete` | Listens for `verdict` |
| An `evidenceCards` array with an appending reducer | Does not exist. Cards are fetched at the end |
| The backend starts a Cloudflare tunnel | A frontend script, started by a person |
| A mobile intake page uploads to a desktop queue | No mobile route. The same page on a phone |
| Synchronised zoom **and pan** | **There is no pan.** A shared zoom level only |
| Bounding boxes drawn as SVG on a canvas | Plain absolutely positioned boxes over an image |
| Green, red, and yellow boxes for pass, fail, and low confidence | Boxes are coloured by component type |
| Hover tooltips on the boxes | The boxes cannot be clicked. No tooltips |
| Client-side image dimension validation | Thumbnails are generated, but there is no size check |
| A raw JSON drawer on the evidence card | Does not exist |
| Filter reports by vendor, verdict, and date range | Free text search, a verdict filter, and a policy filter. No date range, no vendor dropdown |
| Lazy loading and code splitting | One bundle, no lazy loading |
| 7 shared and 4 inspection components | 7 shared and 8 inspection |
| A `useInspectionDetail` hook | Does not exist |
| The 2.5 second polling interval is set by the server | It is a frontend constant |

**What was correct:** the colour palette, the fonts, the route structure and which pages are
protected, the 2.5 second polling interval itself, the component list apart from the two omissions,
the AuthContext surface, and cleaning up the live connection when the page closes.

---

*Next: [TESTING.md](TESTING.md) for how the code is checked.*
